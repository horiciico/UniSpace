"""Planning units, faculties, ETL binding, exceptions and change requests (D-014 to D-016).

DB tests: they need PostgreSQL (compose `db`); see conftest.py.
"""
from datetime import date, time

import pytest
from sqlalchemy.exc import IntegrityError
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
    RequestStatus,
    RuleChangeRequest,
    Role,
    User,
)


def make_faculty(db: Session, code: str = "dre") -> Faculty:
    faculty = Faculty(code=code, name="Facultatea de Drept")
    db.add(faculty)
    db.flush()
    return faculty


def make_unit(db: Session, faculty: Faculty, external_id: str = "12", **kw) -> PlanningTimeUnit:
    values = dict(
        faculty_id=faculty.id, external_id=external_id, name="Modul 1",
        type=PlanningUnitType.MODULE, start_date=date(2026, 10, 1), end_date=date(2026, 12, 20),
    )
    values.update(kw)
    unit = PlanningTimeUnit(**values)
    db.add(unit)
    db.flush()
    return unit


def make_room(db: Session, name: str = "S02") -> Classroom:
    room = Classroom(name=name, capacity=30)
    db.add(room)
    db.flush()
    return room


def make_activity(db: Session, room: Classroom, **kw) -> Activity:
    values = dict(
        name="Algebra", type=ActivityType.COURSE, priority=Priority.COURSE,
        classroom_id=room.id, day_of_week=1, start_time=time(8, 0), end_time=time(10, 0),
    )
    values.update(kw)
    activity = Activity(**values)
    db.add(activity)
    db.flush()
    return activity


def test_faculty_code_is_unique(db: Session) -> None:
    make_faculty(db, "dre")
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            make_faculty(db, "dre")


def test_planning_unit_end_must_not_precede_start(db: Session) -> None:
    faculty = make_faculty(db)
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            make_unit(db, faculty, start_date=date(2026, 12, 1), end_date=date(2026, 11, 1))


def test_planning_unit_external_id_is_unique_per_faculty(db: Session) -> None:
    faculty = make_faculty(db)
    make_unit(db, faculty, external_id="12")
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            make_unit(db, faculty, external_id="12")


def test_imported_external_id_is_unique_within_a_unit(db: Session) -> None:
    faculty = make_faculty(db)
    unit = make_unit(db, faculty)
    room = make_room(db)
    make_activity(db, room, planning_time_unit_id=unit.id, external_id="c-1")
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            make_activity(db, room, planning_time_unit_id=unit.id, external_id="c-1", day_of_week=2)


def test_bookings_without_external_id_do_not_collide(db: Session) -> None:
    room = make_room(db)
    make_activity(db, room, specific_date=date(2026, 12, 7))
    make_activity(db, room, specific_date=date(2026, 12, 7), start_time=time(12, 0), end_time=time(14, 0))


def test_is_manually_modified_defaults_to_false(db: Session) -> None:
    room = make_room(db)
    activity = make_activity(db, room)
    db.refresh(activity)
    assert activity.is_manually_modified is False
    assert activity.specific_date is None


def test_specific_date_must_fall_on_day_of_week(db: Session) -> None:
    room = make_room(db)
    # 2026-12-07 is a Monday (ISO 1), so day_of_week 1 is right and 2 is wrong.
    make_activity(db, room, specific_date=date(2026, 12, 7), day_of_week=1)
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            make_activity(db, room, specific_date=date(2026, 12, 7), day_of_week=2)


def test_exception_times_must_be_ordered(db: Session) -> None:
    room = make_room(db)
    activity = make_activity(db, room)
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(ActivityException(
                activity_id=activity.id, original_date=date(2026, 12, 7),
                new_start_time=time(12, 0), new_end_time=time(11, 0),
            ))
            db.flush()


def test_exception_stores_reason_and_author(db: Session) -> None:
    room = make_room(db)
    activity = make_activity(db, room)
    prof = User(email="prof@uni.ro", name="Prof", role=Role.PROFESSOR)
    db.add(prof)
    db.flush()
    exc = ActivityException(
        activity_id=activity.id, original_date=date(2026, 12, 7),
        new_start_time=time(12, 0), new_end_time=time(14, 0),
        reason="Sala ocupata", created_by_id=prof.id,
    )
    db.add(exc)
    db.flush()
    db.refresh(exc)
    assert exc.reason == "Sala ocupata"
    assert exc.created_by_id == prof.id


def test_change_request_needs_at_least_one_change(db: Session) -> None:
    room = make_room(db)
    activity = make_activity(db, room)
    prof = User(email="prof2@uni.ro", name="Prof", role=Role.PROFESSOR)
    db.add(prof)
    db.flush()
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(RuleChangeRequest(activity_id=activity.id, requested_by_id=prof.id, reason="x"))
            db.flush()


def test_change_request_day_must_be_iso_weekday(db: Session) -> None:
    room = make_room(db)
    activity = make_activity(db, room)
    prof = User(email="prof3@uni.ro", name="Prof", role=Role.PROFESSOR)
    db.add(prof)
    db.flush()
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(RuleChangeRequest(
                activity_id=activity.id, requested_by_id=prof.id, reason="x", new_day_of_week=0,
            ))
            db.flush()


def test_change_request_starts_pending(db: Session) -> None:
    room = make_room(db)
    activity = make_activity(db, room, parity=Parity.ODD)
    prof = User(email="prof4@uni.ro", name="Prof", role=Role.PROFESSOR)
    db.add(prof)
    db.flush()
    req = RuleChangeRequest(
        activity_id=activity.id, requested_by_id=prof.id, reason="sala schimbata",
        new_classroom_id=make_room(db, "S03").id,
    )
    db.add(req)
    db.flush()
    db.refresh(req)
    assert req.status == RequestStatus.PENDING
