"""A professor's own teaching timetable and the activities they may move (business rules 2-6).

- GET /api/professors/me/timetable?week_start=YYYY-MM-DD: the week's occurrences for the signed-in
  professor, with parity, exceptions and cancellations applied (planning.occurrences).
- GET /api/professors/me/movable-activities: weekly activities and upcoming one-offs, for the
  Move Activity dropdown.

Only a PROFESSOR user has these (403 otherwise). A PROFESSOR with no professors row is unlinked:
`linked` is false and the lists are empty (business rule 6).
"""

import uuid
from collections import defaultdict
from datetime import date, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.availability import day_availability
from app.db import get_db
from app.models import (
    Activity,
    ActivityGroup,
    Classroom,
    PlanningTimeUnit,
    Role,
    Status,
    StudentGroup,
    User,
)
from app.moves import move_occurrence
from app.planning import hhmm, local_today, occurrences, week_monday
from app.professors import get_professor_for_user
from app.routers.schedule import activity_items

router = APIRouter(prefix="/api/professors", tags=["professors"])


class MoveIn(BaseModel):
    original_date: date
    new_date: date
    start_time: time
    end_time: time
    new_classroom_id: uuid.UUID


def _require_professor(user: User) -> None:
    if user.role != Role.PROFESSOR:
        raise HTTPException(403, "Only professors have a teaching timetable.")


@router.get("/me/timetable")
def my_timetable(
    week_start: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """The Monday-to-Sunday week that contains `week_start` (today when omitted)."""
    _require_professor(user)
    monday = week_monday(week_start or local_today())
    sunday = monday + timedelta(days=6)
    professor = get_professor_for_user(db, user)
    base = {"week_start": monday.isoformat(), "week_end": sunday.isoformat()}
    if professor is None:
        return {**base, "linked": False, "professor_id": None, "activities": []}

    found = occurrences(db, monday, sunday, Activity.professor_id == professor.id)
    return {
        **base,
        "linked": True,
        "professor_id": str(professor.id),
        "activities": activity_items(db, found),
    }


@router.get("/me/movable-activities")
def my_movable_activities(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    """The professor's weekly activities still running, and one-offs that are not yet past."""
    _require_professor(user)
    professor = get_professor_for_user(db, user)
    if professor is None:
        return {"linked": False, "activities": []}

    today = local_today()
    rows = db.execute(
        select(Activity, Classroom.name)
        .join(Classroom, Classroom.id == Activity.classroom_id)
        .outerjoin(PlanningTimeUnit, PlanningTimeUnit.id == Activity.planning_time_unit_id)
        .where(
            Activity.professor_id == professor.id,
            Activity.status != Status.CANCELLED,
            or_(
                and_(Activity.specific_date.is_(None), PlanningTimeUnit.end_date >= today),
                Activity.specific_date >= today,
            ),
        )
        .order_by(Activity.day_of_week, Activity.start_time, Activity.name)
    ).all()
    # The groups of each activity: their ids (for the availability check) and names (for the list).
    groups: dict[uuid.UUID, list[tuple[uuid.UUID, str]]] = defaultdict(list)
    if rows:
        for activity_id, group_id, group_name in db.execute(
            select(ActivityGroup.activity_id, StudentGroup.id, StudentGroup.name)
            .join(StudentGroup, StudentGroup.id == ActivityGroup.group_id)
            .where(ActivityGroup.activity_id.in_([activity.id for activity, _ in rows]))
        ).all():
            groups[activity_id].append((group_id, group_name))
    return {
        "linked": True,
        "activities": [
            {
                "id": str(activity.id),
                "title": activity.name,
                "activity_type": activity.type.value,
                "day_of_week": activity.day_of_week,
                "start_time": hhmm(activity.start_time),
                "end_time": hhmm(activity.end_time),
                "room_name": room_name,
                "is_recurring": activity.specific_date is None,
                "specific_date": (
                    activity.specific_date.isoformat() if activity.specific_date else None
                ),
                "group_ids": [
                    str(gid) for gid, _ in sorted(groups[activity.id], key=lambda g: g[1])
                ],
                "groups": sorted(name for _, name in groups[activity.id]),
            }
            for activity, room_name in rows
        ],
    }


@router.get("/me/availability")
def my_availability(
    day: date = Query(alias="date"),
    group_ids: list[uuid.UUID] = Query(default=[]),
    exclude_activity_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Each module of the day: whether the professor and the given groups are free, and which
    bookable rooms are free. `exclude_activity_id` ignores that activity's occurrence on `day`."""
    _require_professor(user)
    professor = get_professor_for_user(db, user)
    if professor is None:
        raise HTTPException(403, "Your account is not linked to a professor record.")
    groups: list[tuple[uuid.UUID, str]] = []
    for group_id in dict.fromkeys(group_ids):
        group = db.get(StudentGroup, group_id)
        if group is None:
            raise HTTPException(404, "Group not found")
        groups.append((group.id, group.name))
    return {
        "date": day.isoformat(),
        "professor_id": str(professor.id),
        "modules": day_availability(db, day, professor.id, groups, exclude_activity_id),
    }


@router.post("/me/activities/{activity_id}/move")
def move_activity(
    activity_id: uuid.UUID,
    body: MoveIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Move one occurrence of an activity the signed-in professor teaches (D-026, step 3)."""
    _require_professor(user)
    professor = get_professor_for_user(db, user)
    if professor is None:
        raise HTTPException(403, "Your account is not linked to a professor record.")
    new, room = move_occurrence(
        db,
        professor,
        user,
        activity_id,
        body.original_date,
        body.new_date,
        body.start_time,
        body.end_time,
        body.new_classroom_id,
        local_today(),
    )
    return {
        "id": str(new.id),
        "original_date": body.original_date.isoformat(),
        "date": body.new_date.isoformat(),
        "start_time": hhmm(new.start_time),
        "end_time": hhmm(new.end_time),
        "room_id": str(room.id),
        "room_name": room.name,
        "title": new.name,
    }
