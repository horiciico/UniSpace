"""Which modules of a day a professor and some groups can use, and which rooms are free in each.

Built on planning.occurrences, so parity, one-offs, exceptions, cancellations and moves apply the
same way as on the timetable. Approved bookings block a room; pending ones do not (D-023). Only
bookable rooms are listed, as in the free-room search.

Reusable by PR 2 (Schedule Exam): it takes any list of groups and a day.
"""

import uuid
from collections import defaultdict
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.academic_calendar import day_without_classes, teaching_faculty_ids
from app.models import AcademicPeriodType, Activity, ActivityGroup, Classroom, Faculty
from app.planning import MODULES, hhmm, occurrences
from app.routers.bookings import approved_busy

Busy = tuple[str, time, time]  # (what is on, start, end)
BLOCKED = {AcademicPeriodType.HOLIDAY: "Holiday.", AcademicPeriodType.EXAM_SESSION: "Exam session."}


def _overlaps(start: time, end: time, other_start: time, other_end: time) -> bool:
    return start < other_end and other_start < end


def _busy_of(db: Session, day: date, exclude: uuid.UUID | None, *conditions) -> list[Busy]:
    """Occurrences of the conditions on the day, minus the excluded activity's own occurrence."""
    found: list[Busy] = []
    for o in occurrences(db, day, day, *conditions):
        if exclude is not None and o.activity.id == exclude:
            continue
        assert o.start_time is not None and o.end_time is not None
        found.append((o.activity.name, o.start_time, o.end_time))
    return found


def _first_clash(busy: list[Busy], start: time, end: time) -> Busy | None:
    for item in busy:
        if _overlaps(start, end, item[1], item[2]):
            return item
    return None


def _day_state(
    db: Session,
    day: date,
    professor_id: uuid.UUID,
    groups: list[tuple[uuid.UUID, str]],
    exclude_activity_id: uuid.UUID | None,
):
    """What is busy on the day: the professor, each group, each room; and the bookable rooms."""
    professor_busy = _busy_of(db, day, exclude_activity_id, Activity.professor_id == professor_id)
    group_busy: list[tuple[str, list[Busy]]] = []
    for group_id, group_name in groups:
        in_group = Activity.id.in_(
            select(ActivityGroup.activity_id).where(ActivityGroup.group_id == group_id)
        )
        group_busy.append((group_name, _busy_of(db, day, exclude_activity_id, in_group)))

    room_busy: dict[uuid.UUID, list[tuple[time, time]]] = defaultdict(list)
    for o in occurrences(db, day, day):
        if exclude_activity_id is not None and o.activity.id == exclude_activity_id:
            continue
        assert o.start_time is not None and o.end_time is not None
        room_busy[o.activity.classroom_id].append((o.start_time, o.end_time))
    for room_id, start, end in approved_busy(db, day):
        room_busy[room_id].append((start, end))

    # Each room with the name of the faculty that owns it (None for a campus room).
    rooms = db.execute(
        select(Classroom, Faculty.name)
        .outerjoin(Faculty, Faculty.id == Classroom.faculty_id)
        .where(Classroom.is_bookable.is_(True))
        .order_by(Classroom.name)
    ).all()
    return professor_busy, group_busy, room_busy, rooms


def _reason(start: time, end: time, professor_busy, group_busy) -> str | None:
    """Why the professor or a group cannot use start-end, or None. Names what is on."""
    reasons: list[str] = []
    clash = _first_clash(professor_busy, start, end)
    if clash is not None:
        reasons.append(f"Professor busy: {clash[0]} {hhmm(clash[1])}-{hhmm(clash[2])}.")
    for group_name, busy in group_busy:
        clash = _first_clash(busy, start, end)
        if clash is not None:
            reasons.append(f"Group {group_name} busy: {clash[0]}.")
    return " ".join(reasons) if reasons else None


def _free_rooms(rooms, room_busy, start: time, end: time) -> list[dict]:
    """The bookable rooms with no occurrence or approved booking that overlaps start-end."""
    return [
        {
            "id": str(room.id),
            "name": room.name,
            "capacity": room.capacity,
            "has_projector": room.has_projector,
            "is_field_verified": room.is_field_verified,
            "faculty_id": str(room.faculty_id) if room.faculty_id else None,
            "faculty_name": faculty_name,
        }
        for room, faculty_name in rooms
        if not any(_overlaps(start, end, s, e) for s, e in room_busy.get(room.id, []))
    ]


def day_availability(
    db: Session,
    day: date,
    professor_id: uuid.UUID,
    groups: list[tuple[uuid.UUID, str]],
    exclude_activity_id: uuid.UUID | None = None,
) -> list[dict]:
    """One entry per module of the day: whether the professor and every group are free in it,
    the reason when not, and the bookable rooms free in it. On a holiday or exam session of the
    moved activity's faculty no module is available, and rooms of such a faculty are left out; an
    exam is only stopped by a holiday (D-029)."""
    moved = db.get(Activity, exclude_activity_id) if exclude_activity_id else None
    blocked = (
        day_without_classes(db, day, teaching_faculty_ids(db, moved), moved) if moved else None
    )
    professor_busy, group_busy, room_busy, rooms = _day_state(
        db, day, professor_id, groups, exclude_activity_id
    )
    closed = {
        faculty_id
        for faculty_id in {room.faculty_id for room, _ in rooms}
        if day_without_classes(db, day, {faculty_id}, moved) is not None
    }
    rooms = [row for row in rooms if row[0].faculty_id not in closed]
    modules = []
    for start, end in MODULES:
        reason = _reason(start, end, professor_busy, group_busy)
        if blocked:
            reason = " ".join(filter(None, [BLOCKED[blocked], reason]))
        modules.append(
            {
                "start_time": hhmm(start),
                "end_time": hhmm(end),
                "available": reason is None,
                "conflict_reason": reason,
                "free_classrooms": _free_rooms(rooms, room_busy, start, end),
            }
        )
    return modules


def interval_availability(
    db: Session,
    day: date,
    start: time,
    end: time,
    professor_id: uuid.UUID,
    groups: list[tuple[uuid.UUID, str]],
    exclude_activity_id: uuid.UUID | None = None,
) -> dict:
    """Any start-end interval of the day (an exam can be 2 hours, or start at 14:30). Same shape as
    a module entry. Overlap decides: a class that starts inside the interval takes it."""
    professor_busy, group_busy, room_busy, rooms = _day_state(
        db, day, professor_id, groups, exclude_activity_id
    )
    reason = _reason(start, end, professor_busy, group_busy)
    return {
        "start_time": hhmm(start),
        "end_time": hhmm(end),
        "available": reason is None,
        "conflict_reason": reason,
        "free_classrooms": _free_rooms(rooms, room_busy, start, end),
    }


def slot_clashes(
    db: Session,
    day: date,
    start: time,
    end: time,
    professor_id: uuid.UUID,
    groups: list[tuple[uuid.UUID, str]],
    room_id: uuid.UUID,
    exclude_activity_id: uuid.UUID | None = None,
) -> list[str]:
    """Why the professor, a group or the room cannot use start-end on the day; [] when all are free.

    The excluded activity's own occurrence on `day` does not count (a move's own original slot).
    Approved bookings block the room; pending ones do not (D-023).
    """
    reasons: list[str] = []
    clash = _first_clash(
        _busy_of(db, day, exclude_activity_id, Activity.professor_id == professor_id), start, end
    )
    if clash is not None:
        reasons.append(f"Professor busy: {clash[0]} {hhmm(clash[1])}-{hhmm(clash[2])}.")
    for group_id, group_name in groups:
        in_group = Activity.id.in_(
            select(ActivityGroup.activity_id).where(ActivityGroup.group_id == group_id)
        )
        clash = _first_clash(_busy_of(db, day, exclude_activity_id, in_group), start, end)
        if clash is not None:
            reasons.append(f"Group {group_name} busy: {clash[0]}.")

    room_busy = _busy_of(db, day, exclude_activity_id, Activity.classroom_id == room_id)
    room_busy += [
        ("an approved booking", booked_start, booked_end)
        for booked_room, booked_start, booked_end in approved_busy(db, day)
        if booked_room == room_id
    ]
    clash = _first_clash(room_busy, start, end)
    if clash is not None:
        reasons.append(f"Room busy: {clash[0]} {hhmm(clash[1])}-{hhmm(clash[2])}.")
    return reasons
