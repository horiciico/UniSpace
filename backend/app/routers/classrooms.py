import uuid
from datetime import date, time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Classroom, Faculty
from app.planning import BOOKING_END, NoModuleLeft, booking_window, hhmm, local_today, occurrences
from app.routers.bookings import approved_busy

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
    """Rooms free for a window of whole modules (planning.booking_window).

    Without times: the module that contains now (the next one during a break). start_time
    alone works the same way from that time. Both: from the start of a module to the end of a
    module. Only bookable rooms. Approved bookings block a room; pending ones do not. start_time
    and end_time are the searched window; free_until is the next start that day, or 21:10 when
    nothing follows. Sorted: verified first, then the latest free_until, then name.
    """
    today = local_today()
    day = day or today
    try:
        window_start, window_end = booking_window(start_time, end_time)
    except NoModuleLeft as exc:
        # Only the current day is closed after the last module. A later day has rooms
        # bookable by module, but none starts at this time, so nothing is free for it.
        if day > today:
            return []
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

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
    for room_id, booked_start, booked_end in approved_busy(db, day):
        busy.setdefault(room_id, []).append((booked_start, booked_end))

    found: list[tuple[dict, time]] = []
    for room, faculty_name in rooms:
        intervals = busy.get(room.id, [])
        if any(s < window_end and e > window_start for s, e in intervals):
            continue
        next_starts = [s for s, _ in intervals if s >= window_end]
        free_until = min(next_starts) if next_starts else BOOKING_END
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
                "start_time": hhmm(window_start),
                "end_time": hhmm(window_end),
                "free_until": hhmm(free_until),
            },
            free_until,
        ))

    def sort_key(item: tuple[dict, time]):
        room, free_until = item
        return (0 if room["is_field_verified"] else 1, -_minutes(free_until), room["name"])

    return [room for room, _ in sorted(found, key=sort_key)]
