"""The shared occurrences helper (planning.occurrences) with exceptions (D-016, Q-017).

A cancelled activity or a cancelled occurrence does not happen. A moved occurrence happens on its
new day and at its new time, not at the old one. Moving rooms is not handled yet (Q-017).
DB tests: they need PostgreSQL (compose `db`); see conftest.py.
"""

import uuid
from datetime import date, time

from sqlalchemy.orm import Session

from app.models import (
    Activity,
    ActivityException,
    ActivityType,
    Classroom,
    Faculty,
    Parity,
    PlanningTimeUnit,
    PlanningUnitType,
    Priority,
    Status,
)
from app.planning import occurrences

MONDAY = date(2026, 12, 14)  # week 11, ODD
TUESDAY = date(2026, 12, 15)
NEXT_MONDAY = date(2026, 12, 21)


def make_world(db: Session) -> tuple[Classroom, PlanningTimeUnit]:
    tag = uuid.uuid4().hex[:8]
    faculty = Faculty(code=f"o{tag}", name="Facultatea de Test")
    db.add(faculty)
    db.flush()
    unit = PlanningTimeUnit(
        faculty_id=faculty.id,
        external_id=int(tag, 16) % 2_000_000_000,
        year=2026,
        name="Semestrul 1",
        type=PlanningUnitType.SEMESTER,
        start_date=date(2026, 10, 5),
        end_date=date(2027, 1, 31),
    )
    db.add(unit)
    db.flush()
    room = Classroom(name=f"O-{tag}", capacity=30, external_id=f"o-{tag}")
    db.add(room)
    db.flush()
    return room, unit


def make_course(db: Session, room: Classroom, unit: PlanningTimeUnit, **kw) -> Activity:
    values = dict(
        name="Algebra",
        type=ActivityType.COURSE,
        priority=Priority.COURSE,
        classroom_id=room.id,
        day_of_week=1,
        start_time=time(10, 0),
        end_time=time(12, 0),
        parity=Parity.ALL,
        planning_time_unit_id=unit.id,
        external_id=f"c-{uuid.uuid4().hex[:8]}",
    )
    values.update(kw)
    course = Activity(**values)
    db.add(course)
    db.flush()
    return course


def in_room(room: Classroom):
    return Activity.classroom_id == room.id


def test_a_plain_course_happens_on_its_weekday(db: Session) -> None:
    room, unit = make_world(db)
    make_course(db, room, unit)

    found = occurrences(db, MONDAY, MONDAY, in_room(room))

    assert [(o.day, o.start_time, o.end_time) for o in found] == [
        (MONDAY, time(10, 0), time(12, 0))
    ]


def test_an_activity_with_status_cancelled_does_not_happen(db: Session) -> None:
    room, unit = make_world(db)
    make_course(db, room, unit, status=Status.CANCELLED)

    assert occurrences(db, MONDAY, MONDAY, in_room(room)) == []


def test_a_cancelled_occurrence_does_not_happen_but_the_others_do(db: Session) -> None:
    room, unit = make_world(db)
    course = make_course(db, room, unit)
    db.add(ActivityException(activity_id=course.id, original_date=MONDAY, is_cancelled=True))
    db.flush()

    assert occurrences(db, MONDAY, MONDAY, in_room(room)) == []
    assert [o.day for o in occurrences(db, MONDAY, NEXT_MONDAY, in_room(room))] == [NEXT_MONDAY]


def test_a_moved_occurrence_happens_on_its_new_day_and_time(db: Session) -> None:
    room, unit = make_world(db)
    course = make_course(db, room, unit)
    db.add(
        ActivityException(
            activity_id=course.id,
            original_date=MONDAY,
            new_date=TUESDAY,
            new_start_time=time(14, 0),
            new_end_time=time(15, 30),
        )
    )
    db.flush()

    assert occurrences(db, MONDAY, MONDAY, in_room(room)) == []
    moved = occurrences(db, TUESDAY, TUESDAY, in_room(room))
    assert [(o.day, o.start_time, o.end_time) for o in moved] == [
        (TUESDAY, time(14, 0), time(15, 30))
    ]


def test_a_moved_occurrence_can_keep_its_day_and_change_only_the_time(db: Session) -> None:
    room, unit = make_world(db)
    course = make_course(db, room, unit)
    db.add(
        ActivityException(
            activity_id=course.id,
            original_date=MONDAY,
            new_start_time=time(13, 0),
            new_end_time=time(14, 30),
        )
    )
    db.flush()

    found = occurrences(db, MONDAY, MONDAY, in_room(room))
    assert [(o.day, o.start_time, o.end_time) for o in found] == [
        (MONDAY, time(13, 0), time(14, 30))
    ]


def test_a_move_to_a_day_outside_the_window_is_not_in_it(db: Session) -> None:
    room, unit = make_world(db)
    course = make_course(db, room, unit)
    db.add(ActivityException(activity_id=course.id, original_date=MONDAY, new_date=NEXT_MONDAY))
    db.flush()

    assert occurrences(db, MONDAY, TUESDAY, in_room(room)) == []
