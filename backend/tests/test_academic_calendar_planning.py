"""The academic calendar in planning (D-027, Tasks 3 and 4).

Task 3: weekly activities are suppressed on EXAM_SESSION and HOLIDAY dates; one-offs stay.
Task 4: the booking times follow the period type (modules, half hours, or closed).
DB tests: they need PostgreSQL (compose `db`); see conftest.py.
"""

import uuid
from datetime import date, time

import pytest
from sqlalchemy.orm import Session

from app.models import (
    AcademicPeriod,
    AcademicPeriodType,
    Activity,
    ActivityType,
    Classroom,
    Faculty,
    Parity,
    PlanningTimeUnit,
    PlanningUnitType,
    Priority,
)
from app.planning import occurrences, validate_booking_times
from app.routers.bookings import clash

TEACHING_DAY = date(2026, 12, 7)  # a Monday, no period
EXAM_DAY = date(2026, 12, 14)  # a Monday
HOLIDAY_DAY = date(2026, 12, 21)  # a Monday


@pytest.fixture
def world(db: Session) -> dict:
    tag = uuid.uuid4().hex[:8]
    faculty = Faculty(code=f"k{tag}", name="Facultatea de Test")
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
    room = Classroom(name=f"K-{tag}", capacity=30, external_id=f"k-{tag}")
    db.add_all([unit, room])
    db.flush()
    db.add_all(
        [
            AcademicPeriod(
                name="Sesiune",
                type=AcademicPeriodType.EXAM_SESSION,
                start_date=date(2026, 12, 10),
                end_date=date(2026, 12, 18),
            ),
            AcademicPeriod(
                name="Vacanta",
                type=AcademicPeriodType.HOLIDAY,
                start_date=date(2026, 12, 20),
                end_date=date(2027, 1, 3),
            ),
        ]
    )
    db.flush()
    return {"unit": unit, "room": room, "tag": tag}


def activity(db: Session, world: dict, **kw) -> Activity:
    values = dict(
        name="Algebra",
        type=ActivityType.COURSE,
        priority=Priority.COURSE,
        classroom_id=world["room"].id,
        day_of_week=1,
        start_time=time(10, 0),
        end_time=time(12, 0),
        parity=Parity.ALL,
        planning_time_unit_id=world["unit"].id,
        external_id=f"a-{uuid.uuid4().hex[:8]}",
    )
    values.update(kw)
    row = Activity(**values)
    db.add(row)
    db.flush()
    return row


def in_room(world: dict):
    return Activity.classroom_id == world["room"].id


# --- Task 3: occurrences ---------------------------------------------------------------


def test_a_weekly_course_runs_on_teaching_dates_but_not_in_exam_session_or_holiday(
    db: Session, world: dict
) -> None:
    activity(db, world)

    def days(day: date) -> list[date]:
        return [o.day for o in occurrences(db, day, day, in_room(world))]

    assert days(TEACHING_DAY) == [TEACHING_DAY]  # no period covers it
    assert days(EXAM_DAY) == []
    assert days(HOLIDAY_DAY) == []


def test_a_period_edge_day_is_inside_the_period(db: Session, world: dict) -> None:
    activity(db, world, day_of_week=4)  # Thursday 2026-12-10, the first exam day
    activity(db, world, day_of_week=5, external_id="fri")  # Friday 2026-12-18, the last
    activity(db, world, day_of_week=6, external_id="sat")  # Saturday 2026-12-19, after it

    found = occurrences(db, date(2026, 12, 7), date(2026, 12, 19), in_room(world))

    assert [o.day for o in found] == [date(2026, 12, 19)]


def test_a_range_across_periods_drops_only_the_suppressed_weeks(db: Session, world: dict) -> None:
    activity(db, world)
    found = occurrences(db, date(2026, 12, 1), date(2027, 1, 11), in_room(world))
    # Mondays: 12-07 teaching, 12-14 exam, 12-21 and 12-28 holiday, 01-04 and 01-11 teaching
    assert [o.day for o in found] == [date(2026, 12, 7), date(2027, 1, 4), date(2027, 1, 11)]


def test_a_one_off_activity_stays_in_an_exam_session_and_blocks_conflicts(
    db: Session, world: dict
) -> None:
    exam = activity(
        db,
        world,
        name="Examen",
        type=ActivityType.EXAM,
        priority=Priority.EXAM,
        specific_date=EXAM_DAY,
        start_time=time(10, 0),
        end_time=time(13, 0),
        external_id="exam",
    )
    activity(db, world)  # the weekly course in the same room is suppressed

    found = occurrences(db, EXAM_DAY, EXAM_DAY, in_room(world))
    assert [o.activity.id for o in found] == [exam.id]
    reason = clash(db, world["room"].id, EXAM_DAY, time(12, 0), time(14, 0))
    assert reason is not None and "Examen" in reason
    assert clash(db, world["room"].id, EXAM_DAY, time(13, 0), time(14, 0)) is None


def test_a_one_off_activity_stays_in_a_holiday(db: Session, world: dict) -> None:
    activity(db, world, specific_date=HOLIDAY_DAY, external_id="one")
    assert len(occurrences(db, HOLIDAY_DAY, HOLIDAY_DAY, in_room(world))) == 1


def test_a_weekly_course_does_not_block_a_booking_in_an_exam_session(
    db: Session, world: dict
) -> None:
    activity(db, world)
    assert clash(db, world["room"].id, EXAM_DAY, time(10, 0), time(11, 0)) is None
    assert clash(db, world["room"].id, TEACHING_DAY, time(10, 0), time(11, 0)) is not None


# --- Task 4: the booking times ----------------------------------------------------------

T, E, H = (
    AcademicPeriodType.TEACHING,
    AcademicPeriodType.EXAM_SESSION,
    AcademicPeriodType.HOLIDAY,
)


@pytest.mark.parametrize(
    ("kind", "start", "end", "ok"),
    [
        (T, time(8, 0), time(9, 30), True),
        (T, time(9, 0), time(10, 0), False),  # not modules
        (E, time(9, 0), time(10, 0), True),
        (E, time(8, 0), time(22, 0), True),
        (E, time(10, 0), time(13, 0), True),
        (E, time(8, 0), time(9, 30), True),  # half-hour steps
        (E, time(8, 30), time(10, 0), True),
        (E, time(8, 15), time(10, 0), False),
        (E, time(8, 0), time(9, 40), False),
        (E, time(9, 0), time(9, 30), False),  # under one hour
        (E, time(10, 0), time(10, 0), False),  # under one hour
        (E, time(11, 0), time(10, 0), False),
        (E, time(7, 0), time(9, 0), False),  # before 08:00
        (E, time(21, 0), time(23, 0), False),  # after 22:00
        (E, time(10, 0, 30), time(11, 0), False),
        (H, time(8, 0), time(9, 30), False),
        (H, time(9, 0), time(10, 0), False),
    ],
)
def test_validate_booking_times(kind, start, end, ok) -> None:
    if ok:
        assert validate_booking_times(kind, start, end) == (start, end)
    else:
        with pytest.raises(ValueError):
            validate_booking_times(kind, start, end)
