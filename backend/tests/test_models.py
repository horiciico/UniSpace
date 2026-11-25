"""Scheduling schema tests. Most need PostgreSQL (compose `db`); see conftest.py."""

import uuid
from datetime import date, time

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Base
from app.models import (
    Activity,
    ActivityException,
    ActivityType,
    Booking,
    BookingStatus,
    Classroom,
    Parity,
    Priority,
    Professor,
    Role,
    Status,
    StudentGroup,
    User,
)


def test_all_tables_and_enums_registered() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "student_groups",
        "classrooms",
        "activities",
        "activity_exceptions",
        "invitations",
        "user_invitations",
        "faculties",
        "planning_time_units",
        "rule_change_requests",
        "activity_groups",
        "professors",
        "bookings",
    }
    assert [s.value for s in BookingStatus] == ["pending", "approved", "rejected", "cancelled"]
    assert [p.value for p in Priority] == [1, 2, 3, 4, 5]
    assert (
        Priority.COURSE
        > Priority.EXAM
        > Priority.OFFICIAL_FACULTY
        > Priority.STUDENT_ORG
        > Priority.STUDENT
    )
    assert {r.name for r in Role} == {"STUDENT", "PROFESSOR", "STUDENT_ORG", "ADMIN"}
    assert {t.name for t in ActivityType} == {"COURSE", "LAB", "SEMINAR", "EXAM", "RESERVATION"}
    assert {p.name for p in Parity} == {"ALL", "EVEN", "ODD", "CUSTOM"}
    assert {s.name for s in Status} == {"APPROVED", "BUMPED_PENDING", "CANCELLED"}


def make_room(db: Session, name: str = "S02") -> Classroom:
    room = Classroom(name=name, capacity=30)
    db.add(room)
    db.flush()
    return room


def make_activity(db: Session, room: Classroom, **kw) -> Activity:
    values = dict(
        name="Algebra",
        type=ActivityType.COURSE,
        priority=Priority.COURSE,
        classroom_id=room.id,
        day_of_week=1,
        start_time=time(8, 0),
        end_time=time(10, 0),
    )
    values.update(kw)
    activity = Activity(**values)
    db.add(activity)
    db.flush()
    return activity


def test_invalid_values_are_rejected(db: Session) -> None:
    room = make_room(db)
    bad = [
        dict(priority=6),
        dict(priority=0),
        dict(day_of_week=0),
        dict(day_of_week=8),
        dict(start_time=time(10, 0), end_time=time(10, 0)),
        dict(start_time=time(11, 0), end_time=time(10, 0)),
        dict(parity=Parity.CUSTOM),
    ]
    for kw in bad:
        with pytest.raises(IntegrityError), db.begin_nested():
            make_activity(db, room, **kw)


def test_overlap_query_uses_time_range(db: Session) -> None:
    room = make_room(db)
    other = make_room(db, "S03")
    a = make_activity(db, room)  # Monday 08:00-10:00
    make_activity(db, other)  # same slot, other room
    make_activity(db, room, day_of_week=2)  # other day

    def clashes(start: str, end: str) -> list:
        return db.scalars(
            select(Activity.id).where(
                Activity.classroom_id == room.id,
                Activity.day_of_week == 1,
                Activity.time_range.op("&&")(text(f"int4range({start}, {end}, '[)')")),
            )
        ).all()

    assert clashes("540", "660") == [a.id]  # 09:00-11:00 partial overlap
    assert clashes("420", "540") == [a.id]  # 07:00-09:00 partial overlap
    assert clashes("480", "600") == [a.id]  # identical
    assert clashes("600", "720") == []  # adjacent after
    assert clashes("360", "480") == []  # adjacent before


def test_relationships_round_trip(db: Session) -> None:
    room = make_room(db)
    alt = make_room(db, "S04")
    user = User(email="p@uni.ro", name="Prof", role=Role.PROFESSOR)
    group = StudentGroup(name="332CA")
    db.add_all([user, group])
    db.flush()
    a = make_activity(db, room, user_id=user.id, group_id=group.id, alt_classroom_id=alt.id)
    exc = ActivityException(
        activity_id=a.id, original_date=__import__("datetime").date(2026, 11, 16), is_cancelled=True
    )
    db.add(exc)
    db.flush()
    db.refresh(a)

    assert a.status == Status.APPROVED
    assert a.parity == Parity.ALL
    assert a.user is user and a in user.activities
    assert a.group is group and a in group.activities
    assert a.classroom is room and a in room.activities
    assert a.alt_classroom is alt
    assert a.exceptions == [exc] and exc.activity is a


def test_email_is_unique(db: Session) -> None:
    db.add(User(email="x@uni.ro", name="A", role=Role.STUDENT))
    db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(User(email="x@uni.ro", name="B", role=Role.STUDENT))
        db.flush()


def test_professor_list_is_unique_by_email(db: Session) -> None:
    db.add(Professor(id=uuid.uuid4(), name="Popescu Ana", email="ana.popescu@ulbsibiu.ro"))
    db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(Professor(id=uuid.uuid4(), name="Popescu Ana 2", email="ana.popescu@ulbsibiu.ro"))
        db.flush()


def test_professor_links_are_optional_and_not_foreign_keys(db: Session) -> None:
    """activities.professor_id and users.professor_id are nullable UUIDs (no FK to professors)."""
    user = User(email="prof@uni.ro", name="Prof", role=Role.PROFESSOR)
    assert user.professor_id is None
    db.add(user)
    db.flush()
    assert user.professor_id is None

    fk_targets = {
        fk.column.table.name
        for fk in Base.metadata.tables["activities"].columns["professor_id"].foreign_keys
    }
    assert fk_targets == set()
    assert Base.metadata.tables["users"].columns["professor_id"].foreign_keys == set()


def make_booking_user(db: Session) -> User:
    user = User(email="student@uni.ro", name="Student", role=Role.STUDENT)
    db.add(user)
    db.flush()
    return user


def make_booking(db: Session, user: User, room: Classroom, **kw) -> Booking:
    values = dict(
        user_id=user.id,
        classroom_id=room.id,
        specific_date=date(2026, 12, 1),
        start_time=time(8, 0),
        end_time=time(9, 30),
        title="Board game evening",
    )
    values.update(kw)
    booking = Booking(**values)
    db.add(booking)
    db.flush()
    return booking


def test_booking_defaults_to_pending_with_created_at(db: Session) -> None:
    booking = make_booking(db, make_booking_user(db), make_room(db))
    db.refresh(booking)

    assert booking.id is not None
    assert booking.status == BookingStatus.PENDING
    assert booking.created_at is not None


def test_booking_invalid_rows_are_rejected(db: Session) -> None:
    user = make_booking_user(db)
    room = make_room(db)
    bad = [
        dict(start_time=time(10, 0), end_time=time(10, 0)),
        dict(start_time=time(11, 0), end_time=time(10, 0)),
        dict(title=None),
        dict(user_id=None),
        dict(classroom_id=None),
        dict(specific_date=None),
        dict(start_time=None),
        dict(end_time=None),
    ]
    for kw in bad:
        with pytest.raises(IntegrityError), db.begin_nested():
            make_booking(db, user, room, **kw)


def test_booking_foreign_keys_and_indexes(db: Session) -> None:
    table = "bookings"
    insp = inspect(db.connection())
    fks = {fk["constrained_columns"][0]: fk for fk in insp.get_foreign_keys(table)}

    assert fks["user_id"]["referred_table"] == "users"
    assert fks["user_id"]["options"]["ondelete"] == "CASCADE"
    assert fks["classroom_id"]["referred_table"] == "classrooms"
    assert fks["classroom_id"]["options"]["ondelete"] == "RESTRICT"

    indexed = {col for idx in insp.get_indexes(table) for col in idx["column_names"]}
    assert {"user_id", "classroom_id", "specific_date", "status"} <= indexed
    columns = {col["name"]: col for col in insp.get_columns(table)}
    assert not columns["status"][
        "nullable"
    ]  # the ORM default would hide a None, so check the column


def test_deleting_a_user_deletes_their_bookings(db: Session) -> None:
    user = make_booking_user(db)
    make_booking(db, user, make_room(db))
    db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})

    left = db.execute(
        text("SELECT count(*) FROM bookings WHERE user_id = :id"), {"id": user.id}
    ).scalar_one()
    assert left == 0


def test_a_room_with_bookings_cannot_be_deleted(db: Session) -> None:
    room = make_room(db)
    make_booking(db, make_booking_user(db), room)

    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("DELETE FROM classrooms WHERE id = :id"), {"id": room.id})
