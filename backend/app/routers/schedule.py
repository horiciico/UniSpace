import uuid
from collections import Counter, defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Activity, ActivityGroup, Classroom, StudentGroup
from app.planning import hhmm, local_today, occurrences, reference_week, week_info, week_monday

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


@router.get("")
def get_schedule(
    group_id: uuid.UUID | None = None,
    professor: str | None = None,
    room_id: uuid.UUID | None = None,
    day: date | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
) -> dict:
    """The Monday-to-Sunday week that contains `date`, for one group, professor or room."""
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

    # The week comes from the planning unit of the entity's own recurring activities (most often).
    unit_starts = Counter(o.unit_start for o in found if o.unit_start is not None)
    if unit_starts:
        week_no, parity = week_info(unit_starts.most_common(1)[0][0], monday)
    else:
        week_no, parity = reference_week(db, monday)
    return {
        "week_start": monday.isoformat(),
        "week_end": sunday.isoformat(),
        "week_number": week_no,
        "parity": parity.value if parity else None,
        "entity_type": entity_type,
        "entity_label": entity_label,
        "items": items,
    }
