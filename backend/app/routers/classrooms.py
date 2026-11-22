import uuid
from datetime import date, time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Classroom, Faculty
from app.planning import hhmm, local_now, local_today, occurrences

router = APIRouter(prefix="/api/classrooms", tags=["classrooms"])


def faculty_condition(value: str | None):
    """`faculty_id` query value -> a filter on classrooms.faculty_id, or None for no filter.

    "campus" means rooms with no owning faculty (faculty_id IS NULL).
    """
    if value is None:
        return None
    if value == "campus":
        return Classroom.faculty_id.is_(None)
    try:
        return Classroom.faculty_id == uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="faculty_id must be a UUID or 'campus'")


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


@router.get("")
def list_classrooms(faculty_id: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    stmt = select(Classroom).order_by(Classroom.name)
    condition = faculty_condition(faculty_id)
    if condition is not None:
        stmt = stmt.where(condition)
    return [
        {
            "id": str(room.id),
            "name": room.name,
            "faculty_id": str(room.faculty_id) if room.faculty_id else None,
            "capacity": room.capacity,
            "is_bookable": room.is_bookable,
            "is_field_verified": room.is_field_verified,
        }
        for room in db.scalars(stmt).all()
    ]


@router.get("/free")
def free_classrooms(
    faculty_id: str | None = None,
    day: date | None = Query(None, alias="date"),
    start_time: time | None = None,
    end_time: time | None = None,
    min_capacity: int | None = Query(None, ge=0),
    has_projector: bool | None = None,
    only_verified: bool | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    """Rooms free at start_time, or free over [start_time, end_time] when end_time is given.

    Only bookable rooms. free_until is the start of the room's next activity that day
    (null: free for the rest of the day). Sorted: verified first, then the latest
    free_until (no next activity first), then name.
    """
    day = day or local_today()
    start = start_time or local_now().time().replace(second=0, microsecond=0)
    if end_time is not None and end_time <= start:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    stmt = (
        select(Classroom, Faculty.name)
        .outerjoin(Faculty, Faculty.id == Classroom.faculty_id)
        .where(Classroom.is_bookable.is_(True))
    )
    condition = faculty_condition(faculty_id)
    if condition is not None:
        stmt = stmt.where(condition)
    if min_capacity is not None:
        stmt = stmt.where(Classroom.capacity >= min_capacity)
    if has_projector:
        stmt = stmt.where(Classroom.has_projector.is_(True))
    if only_verified:
        stmt = stmt.where(Classroom.is_field_verified.is_(True))
    rooms = db.execute(stmt).all()

    busy: dict[uuid.UUID, list[tuple[time, time]]] = {}
    for occurrence in occurrences(db, day, day):
        activity = occurrence.activity
        busy.setdefault(activity.classroom_id, []).append((activity.start_time, activity.end_time))

    # The window's last moment: the end, or the start when only a moment is checked.
    window_end = end_time or start
    found: list[tuple[dict, time | None]] = []
    for room, faculty_name in rooms:
        intervals = busy.get(room.id, [])
        if end_time is not None:
            taken = any(s < end_time and e > start for s, e in intervals)
        else:
            taken = any(s <= start < e for s, e in intervals)
        if taken:
            continue
        next_starts = [s for s, _ in intervals if s >= window_end]
        free_until = min(next_starts) if next_starts else None
        found.append((
            {
                "id": str(room.id),
                "name": room.name,
                "faculty_id": str(room.faculty_id) if room.faculty_id else None,
                "faculty_name": faculty_name,
                "capacity": room.capacity,
                "has_projector": room.has_projector,
                "has_outlets": room.has_outlets,
                "is_field_verified": room.is_field_verified,
                "free_until": hhmm(free_until) if free_until else None,
            },
            free_until,
        ))

    def sort_key(item: tuple[dict, time | None]):
        room, free_until = item
        # NULLS FIRST, then the later time first (free_until DESC).
        until_key = (0, 0) if free_until is None else (1, -_minutes(free_until))
        return (0 if room["is_field_verified"] else 1, until_key, room["name"])

    return [room for room, _ in sorted(found, key=sort_key)]
