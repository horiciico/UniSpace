"""Scheduling schema tests. Tests 2-4 need PostgreSQL (compose `db`); they run the
real Alembic migration, then roll every test back."""
from collections.abc import Iterator
from datetime import time

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Base, engine
from app.models import (
    Activity,
    ActivityType,
    Classroom,
    EventException,
    Parity,
    Priority,
    Role,
    Status,
    StudentGroup,
    User,
)


def test_all_tables_and_enums_registered() -> None:
    assert set(Base.metadata.tables) == {
        "user", "student_group", "classroom", "activity", "event_exception",
    }
    assert [p.value for p in Priority] == [1, 2, 3, 4, 5]
    assert Priority.COURSE > Priority.EXAM > Priority.OFFICIAL_FACULTY > Priority.STUDENT_ORG > Priority.STUDENT
    assert {r.name for r in Role} == {"STUDENT", "PROFESSOR", "STUDENT_ORG", "ADMIN"}
    assert {t.name for t in ActivityType} == {"COURSE", "LAB", "SEMINAR", "EXAM", "RESERVATION"}
    assert {p.name for p in Parity} == {"ALL", "EVEN", "ODD", "CUSTOM"}
    assert {s.name for s in Status} == {"APPROVED", "BUMPED_PENDING", "CANCELLED"}


@pytest.fixture(scope="session")
def migrated() -> None:
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")


@pytest.fixture
def db(migrated: None) -> Iterator[Session]:
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


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
        with pytest.raises(IntegrityError):
            with db.begin_nested():
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
    exc = EventException(activity_id=a.id, original_date=__import__("datetime").date(2026, 11, 16), is_cancelled=True)
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
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(User(email="x@uni.ro", name="B", role=Role.STUDENT))
            db.flush()
