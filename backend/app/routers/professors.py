"""A professor's own teaching timetable and the activities they may move (business rules 2-6).

- GET /api/professors/me/timetable?week_start=YYYY-MM-DD: the week's occurrences for the signed-in
  professor, with parity, exceptions and cancellations applied (planning.occurrences).
- GET /api/professors/me/movable-activities: weekly activities and upcoming one-offs, for the
  Move Activity dropdown.

Only a PROFESSOR user has these (403 otherwise). A PROFESSOR with no professors row is unlinked:
`linked` is false and the lists are empty (business rule 6).
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Activity, Classroom, PlanningTimeUnit, Role, Status, User
from app.planning import hhmm, local_today, occurrences, week_monday
from app.professors import get_professor_for_user
from app.routers.schedule import activity_items

router = APIRouter(prefix="/api/professors", tags=["professors"])


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
            }
            for activity, room_name in rows
        ],
    }
