"""Loader against PostgreSQL: idempotence, admin protection, stale rows. Runs in the etl image.

Each test rolls back its own writes, the same way backend/tests/conftest.py does.
"""
import uuid
from collections.abc import Iterator
from datetime import date, time

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import (
    Activity,
    ActivityException,
    ActivityGroup,
    ActivityType,
    Classroom,
    Faculty,
    PlanningTimeUnit,
    PlanningUnitType,
    StudentGroup,
)
from etl.schedule.loader import LoadContext, LoadReport, RoomInfo, load_envelope


@pytest.fixture(scope="session")
def migrated() -> None:
    command.upgrade(Config("alembic.ini"), "head")


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


def entry(item_id: int, room_id: str, day: str = "Monday", group: int = 7, subject: str = "Algebra",
          start: str = "08:00", end: str = "10:00", room: str = "Sala 1") -> dict:
    return {
        "id": item_id, "roomId": room_id, "room": room, "roomFacultyId": "tst9", "day": day, "parity": 0,
        "activityType": {"name": "Curs"}, "subject": subject, "professor": "Popescu Ana",
        "studyFormation": {"id": group, "name": f"GRUP_{group}"},
        "timeSlots": [{"startTime": start, "endTime": end}],
    }


def envelope(faculty_code: str, unit_id, items_by_day: dict) -> dict:
    return {
        "faculty_code": faculty_code,
        "planning_time_unit": {"db_id": str(unit_id), "external_id": 1, "name": "Modul 1"},
        "fetched_at": "2026-11-22T10:00:00+00:00",
        "schedule": {"success": True, "data": items_by_day},
    }


def setup_faculty_and_unit(db: Session, code: str) -> tuple[Faculty, PlanningTimeUnit]:
    faculty = Faculty(code=code, name="Test")
    db.add(faculty)
    db.flush()
    unit = PlanningTimeUnit(
        faculty_id=faculty.id, external_id=1, year=2026, name="Modul 1",
        type=PlanningUnitType.MODULE, start_date=date(2026, 9, 30), end_date=date(2026, 11, 30),
        is_current=True,
    )
    db.add(unit)
    db.flush()
    return faculty, unit


def run(db: Session, env: dict, ctx: LoadContext) -> LoadReport:
    report = LoadReport()
    load_envelope(db, env, ctx, report, "test.json")
    return report


def test_first_load_stores_one_row_per_slot_and_the_capacity_rule(db: Session) -> None:
    faculty, unit = setup_faculty_and_unit(db, "tst9")
    room_known, room_unknown = str(uuid.uuid4()), str(uuid.uuid4())
    ctx = LoadContext(
        rooms={room_known: RoomInfo("Sala A", 30, "tst9")},
        faculty_ids={"tst9": faculty.id},
    )
    env = envelope("tst9", unit.id, {
        "Monday": [
            entry(1, room_known, group=7),
            entry(2, room_known, group=8, subject="Analiza"),  # same slot: merged into one row
            entry(3, room_known, room="Sala Online"),  # online: not stored at all
        ],
        "Tuesday": [entry(4, room_unknown, day="Tuesday", room="B208")],  # not in the rooms list
    })

    report = run(db, env, ctx)

    assert report.inserted == 2
    assert report.deduplicated == 1
    assert report.no_room == 1
    assert report.rooms_unknown_capacity == 1
    rows = db.scalars(select(Activity).where(Activity.planning_time_unit_id == unit.id)).all()
    assert len(rows) == 2
    assert all(r.name == "Didactic Activity" and r.priority == 5 for r in rows)
    known = db.scalar(select(Classroom).where(Classroom.external_id == room_known))
    assert known.capacity == 30 and known.faculty_id == faculty.id
    unknown = db.scalar(select(Classroom).where(Classroom.external_id == room_unknown))
    assert unknown.capacity is None and unknown.name == "B208"
    assert db.scalar(select(StudentGroup).where(StudentGroup.external_id == 7)).name == "GRUP_7"


def test_row_stores_the_professor_id_when_its_entries_agree(db: Session) -> None:
    faculty, unit = setup_faculty_and_unit(db, "tstp")
    room = str(uuid.uuid4())
    prof = "3601532c-3e19-4edf-a41f-d1b996f6487b"
    ctx = LoadContext(rooms={room: RoomInfo("Sala A", 30, "tstp")}, faculty_ids={"tstp": faculty.id})
    env = envelope("tstp", unit.id, {
        "Monday": [
            {**entry(1, room), "professorId": prof},
            {**entry(2, room, group=8), "professorId": prof},  # same slot, same professor
        ],
        "Tuesday": [{**entry(3, room, day="Tuesday"), "professorId": prof},
                    {**entry(4, room, day="Tuesday", group=8), "professorId": str(uuid.uuid4())}],
    })

    run(db, env, ctx)

    rows = {r.day_of_week: r for r in db.scalars(select(Activity).where(Activity.planning_time_unit_id == unit.id))}
    assert str(rows[1].professor_id) == prof
    assert rows[2].professor_id is None  # two professors in one slot: left empty


def test_running_twice_creates_nothing_new(db: Session) -> None:
    faculty, unit = setup_faculty_and_unit(db, "tst8")
    room = str(uuid.uuid4())
    ctx = LoadContext(rooms={room: RoomInfo("Sala A", 30, "tst8")}, faculty_ids={"tst8": faculty.id})
    env = envelope("tst8", unit.id, {"Monday": [entry(1, room), entry(2, room, group=8)]})

    run(db, env, ctx)
    again = run(db, env, LoadContext(rooms=ctx.rooms, faculty_ids=ctx.faculty_ids))

    assert again.inserted == 0
    assert again.updated == 0
    assert again.unchanged == 1
    assert again.deleted == 0
    assert len(db.scalars(select(Activity).where(Activity.planning_time_unit_id == unit.id)).all()) == 1


def test_admin_edited_rows_are_never_overwritten(db: Session) -> None:
    faculty, unit = setup_faculty_and_unit(db, "tst7")
    room = str(uuid.uuid4())
    ctx = LoadContext(rooms={room: RoomInfo("Sala A", 30, "tst7")}, faculty_ids={"tst7": faculty.id})
    env = envelope("tst7", unit.id, {"Monday": [entry(1, room)]})
    run(db, env, ctx)

    row = db.scalar(select(Activity).where(Activity.planning_time_unit_id == unit.id))
    row.is_manually_modified = True
    row.start_time = time(9, 0)
    db.flush()

    report = run(db, env, LoadContext(rooms=ctx.rooms, faculty_ids=ctx.faculty_ids))

    assert report.skipped_manual == 1
    db.refresh(row)
    assert row.start_time == time(9, 0)


def test_rows_that_left_the_feed_are_deleted_unless_referenced(db: Session) -> None:
    faculty, unit = setup_faculty_and_unit(db, "tst6")
    room = str(uuid.uuid4())
    classroom = Classroom(name="Sala Z", capacity=20, external_id=room, faculty_id=faculty.id)
    db.add(classroom)
    db.flush()
    gone = Activity(
        name="Didactic Activity", type=ActivityType.COURSE, priority=5, classroom_id=classroom.id,
        day_of_week=5, start_time=time(8, 0), end_time=time(10, 0), planning_time_unit_id=unit.id,
        external_id="gone-1", is_manually_modified=False,
    )
    referenced = Activity(
        name="Didactic Activity", type=ActivityType.COURSE, priority=5, classroom_id=classroom.id,
        day_of_week=5, start_time=time(12, 0), end_time=time(14, 0), planning_time_unit_id=unit.id,
        external_id="gone-2", is_manually_modified=False,
    )
    db.add_all([gone, referenced])
    db.flush()
    db.add(ActivityException(activity_id=referenced.id, original_date=date(2026, 11, 27), is_cancelled=True))
    db.flush()

    ctx = LoadContext(rooms={room: RoomInfo("Sala Z", 20, "tst6")}, faculty_ids={"tst6": faculty.id})
    report = run(db, envelope("tst6", unit.id, {"Monday": [entry(1, room)]}), ctx)

    assert report.deleted == 1
    assert report.kept_referenced == 1
    assert db.get(Activity, gone.id) is None
    assert db.get(Activity, referenced.id) is not None


def test_a_file_for_another_faculty_is_refused(db: Session) -> None:
    faculty, unit = setup_faculty_and_unit(db, "tst5")
    ctx = LoadContext(rooms={}, faculty_ids={"tst5": faculty.id, "other": uuid.uuid4()})
    with pytest.raises(ValueError, match="another faculty"):
        run(db, envelope("other", unit.id, {"Monday": []}), ctx)


def test_a_merged_slot_links_every_study_group_and_a_rerun_keeps_them(db: Session) -> None:
    faculty, unit = setup_faculty_and_unit(db, "tst10")
    room = str(uuid.uuid4())
    ctx = LoadContext(
        rooms={room: RoomInfo("Sala G", 40, "tst10")},
        faculty_ids={"tst10": faculty.id},
    )
    env = envelope("tst10", unit.id, {
        "Monday": [
            entry(1, room, group=7),
            entry(2, room, group=8, subject="Analiza"),  # same slot: one activity, two groups
        ],
    })
    run(db, env, ctx)
    activity = db.scalars(select(Activity).where(Activity.planning_time_unit_id == unit.id)).one()

    def linked_groups() -> set[int]:
        rows = db.scalars(
            select(StudentGroup.external_id)
            .join(ActivityGroup, ActivityGroup.group_id == StudentGroup.id)
            .where(ActivityGroup.activity_id == activity.id)
        ).all()
        return set(rows)

    assert linked_groups() == {7, 8}
    run(db, env, ctx)
    assert linked_groups() == {7, 8}


def test_a_rerun_keeps_the_admin_room_fields_and_updates_only_the_etl_fields(db: Session) -> None:
    faculty, unit = setup_faculty_and_unit(db, "tst11")
    room = str(uuid.uuid4())
    ctx = LoadContext(rooms={room: RoomInfo("Sala A", 30, "tst11")}, faculty_ids={"tst11": faculty.id})
    run(db, envelope("tst11", unit.id, {"Monday": [entry(1, room)]}), ctx)

    classroom = db.scalar(select(Classroom).where(Classroom.external_id == room))
    classroom.is_bookable = False
    classroom.has_projector = True
    classroom.board_type = "smartboard"
    classroom.access_notes = "Cheia la portar"
    classroom.equipment_notes = "24 PC-uri, 10 osciloscoape"
    db.flush()

    rerun = LoadContext(rooms={room: RoomInfo("Sala A bis", 40, "tst11")}, faculty_ids={"tst11": faculty.id})
    run(db, envelope("tst11", unit.id, {"Monday": [entry(1, room)]}), rerun)

    db.refresh(classroom)
    assert (classroom.name, classroom.capacity) == ("Sala A bis", 40)
    assert classroom.is_bookable is False
    assert classroom.has_projector is True
    assert classroom.board_type == "smartboard"
    assert classroom.access_notes == "Cheia la portar"
    assert classroom.equipment_notes == "24 PC-uri, 10 osciloscoape"
