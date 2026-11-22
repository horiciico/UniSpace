import uuid
from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Activity, ActivityGroup, Classroom, PlanningTimeUnit, StudentGroup
from app.planning import hhmm, local_today, occurrences, week_info, week_monday

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


def _timetable_unit(db: Session, faculty_id: uuid.UUID | None, monday: date, sunday: date,
                    conditions: list) -> PlanningTimeUnit | None:
    """The planning unit this week's timetable is drawn from (None: nothing to draw from)."""
    if faculty_id is not None:
        return db.scalars(
            select(PlanningTimeUnit)
            .where(
                PlanningTimeUnit.faculty_id == faculty_id,
                PlanningTimeUnit.start_date <= sunday,
                PlanningTimeUnit.end_date >= monday,
            )
            .order_by(PlanningTimeUnit.start_date.desc())
            .limit(1)
        ).first()
    # The entity's recurring activities in units that cover this week, in any parity, so a week
    # with no classes still has a unit (and a week number).
    rows = db.execute(
        select(Activity.planning_time_unit_id, func.count())
        .join(PlanningTimeUnit, PlanningTimeUnit.id == Activity.planning_time_unit_id)
        .where(
            *conditions,
            Activity.specific_date.is_(None),
            PlanningTimeUnit.start_date <= sunday,
            PlanningTimeUnit.end_date >= monday,
        )
        .group_by(Activity.planning_time_unit_id)
    ).all()
    if not rows:
        return None
    # Most activities first; equal counts go to the larger id, so the choice is stable.
    unit_id = max(rows, key=lambda row: (row[1], str(row[0])))[0]
    return db.get(PlanningTimeUnit, unit_id)


@router.get("")
def get_schedule(
    group_id: uuid.UUID | None = None,
    professor: str | None = None,
    room_id: uuid.UUID | None = None,
    day: date | None = Query(None, alias="date"),
    faculty_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """The Monday-to-Sunday week that contains `date`, for one group, professor or room.

    Only one planning unit is shown: the faculty's unit that covers the week (faculty_id), or
    without a faculty, the unit most of the entity's recurring activities use. One-off rows
    (no planning unit) are always shown.
    """
    name = professor.strip() if professor and professor.strip() else None
    given = [value for value in (group_id, name, room_id) if value is not None]
    if len(given) != 1:
        raise HTTPException(status_code=400, detail="Give exactly one of group_id, professor or room_id")

    monday = week_monday(day or local_today())
    sunday = monday + timedelta(days=6)

    if group_id is not None:
        group = db.get(StudentGroup, group_id)
        if group is None:
            raise HTTPException(status_code=404, detail="Group not found")
        conditions = [Activity.id.in_(select(ActivityGroup.activity_id).where(ActivityGroup.group_id == group_id))]
        entity_type, entity_label = "group", group.name
    elif name is not None:
        conditions = [Activity.professor_name.contains(name, autoescape=True)]
        entity_type, entity_label = "professor", name
    else:
        room = db.get(Classroom, room_id)
        if room is None:
            raise HTTPException(status_code=404, detail="Room not found")
        conditions = [Activity.classroom_id == room_id]
        entity_type, entity_label = "room", room.name

    found = occurrences(db, monday, sunday, *conditions)
    if name is not None:
        # "contains" matched the text; keep only the exact name among the joined names.
        found = [o for o in found if name in [p.strip() for p in (o.activity.professor_name or "").split(" / ")]]

    unit = _timetable_unit(db, faculty_id, monday, sunday, conditions)
    found = [
        o for o in found
        if o.activity.specific_date is not None
        or (unit is not None and o.activity.planning_time_unit_id == unit.id)
    ]

    activity_ids = {o.activity.id for o in found}
    group_names: dict[uuid.UUID, list[str]] = defaultdict(list)
    if activity_ids:
        rows = db.execute(
            select(ActivityGroup.activity_id, StudentGroup.name)
            .join(StudentGroup, StudentGroup.id == ActivityGroup.group_id)
            .where(ActivityGroup.activity_id.in_(activity_ids))
        ).all()
        for activity_id, group_name in rows:
            group_names[activity_id].append(group_name)

    items = []
    for o in sorted(found, key=lambda o: (o.day, o.activity.start_time, o.activity.name)):
        a = o.activity
        items.append({
            "id": str(a.id),
            "title": a.name,
            "activity_type": a.type.value,
            "priority": a.priority,
            "day_of_week": a.day_of_week,
            "date": o.day.isoformat(),
            "start_time": hhmm(a.start_time),
            "end_time": hhmm(a.end_time),
            "parity": a.parity.value,
            "room_id": str(a.classroom_id),
            "room_name": a.classroom.name,
            "professor": a.professor_name,
            "groups": sorted(group_names.get(a.id, [])),
            "is_recurring": a.specific_date is None,
        })

    week_no, parity = week_info(unit.start_date, monday) if unit is not None else (None, None)
    return {
        "week_start": monday.isoformat(),
        "week_end": sunday.isoformat(),
        "week_number": week_no,
        "parity": parity.value if parity else None,
        "entity_type": entity_type,
        "entity_label": entity_label,
        "items": items,
    }
