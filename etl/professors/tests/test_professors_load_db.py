"""Professors upsert against PostgreSQL: idempotent, never deletes, email conflicts reported.

Each test rolls back its own writes, the same way the schedule loader tests do.
"""
import uuid
from collections.abc import Iterator
from datetime import time

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import Activity, ActivityType, Classroom, Priority, Professor, Role, User
from etl.professors.load import LoadReport, build_preferences, sync_professors, upsert_professors


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


def rec(name: str = "Popescu Ana", email: str = "ana@ulbsibiu.ro", id: str | None = None) -> dict:
    return {"id": id or str(uuid.uuid4()), "name": name, "email": email}


def test_first_run_inserts_and_a_rerun_updates_without_duplicates(db: Session) -> None:
    a = rec()
    report = LoadReport()
    upsert_professors(db, [a], report)
    assert report.stored == 1

    again = LoadReport()
    upsert_professors(db, [{**a, "name": "Popescu Ana-Maria"}], again)

    assert again.stored == 1
    rows = db.scalars(select(Professor).where(Professor.id == uuid.UUID(a["id"]))).all()
    assert len(rows) == 1
    assert rows[0].name == "Popescu Ana-Maria"


def test_rows_missing_from_the_latest_load_are_kept(db: Session) -> None:
    kept = rec(email="kept@ulbsibiu.ro")
    upsert_professors(db, [kept], LoadReport())
    upsert_professors(db, [rec(email="other@ulbsibiu.ro")], LoadReport())

    assert db.get(Professor, uuid.UUID(kept["id"])) is not None


def test_an_email_held_by_another_id_is_reported_and_not_stored(db: Session) -> None:
    upsert_professors(db, [rec(email="shared@ulbsibiu.ro")], LoadReport())
    newcomer = rec(name="Other person", email="shared@ulbsibiu.ro")

    report = LoadReport()
    upsert_professors(db, [newcomer], report)

    assert report.stored == 0
    assert report.email_conflicts == [newcomer["id"]]
    assert db.get(Professor, uuid.UUID(newcomer["id"])) is None


def test_preferences_hold_the_stored_email_ids_and_the_activity_professor_ids(db: Session) -> None:
    stored = rec(email="pref@ulbsibiu.ro")
    upsert_professors(db, [stored], LoadReport())
    room = Classroom(name="PREF", capacity=10)
    db.add(room)
    db.flush()
    used_id = uuid.uuid4()
    db.add(Activity(
        name="Didactic Activity", type=ActivityType.COURSE, priority=Priority.COURSE, classroom_id=room.id,
        day_of_week=1, start_time=time(8, 0), end_time=time(10, 0), professor_id=used_id,
    ))
    db.flush()

    emails, used = build_preferences(db)

    assert emails["pref@ulbsibiu.ro"] == stored["id"]
    assert str(used_id) in used


def test_two_ids_with_one_email_in_one_load_store_the_first_only(db: Session) -> None:
    first = rec(id="00000000-0000-4000-8000-000000000001", email="dup@ulbsibiu.ro")
    second = rec(id="00000000-0000-4000-8000-000000000002", email="dup@ulbsibiu.ro")

    report = LoadReport()
    upsert_professors(db, [first, second], report)

    assert report.stored == 1
    assert report.email_conflicts == [second["id"]]
    assert db.get(Professor, uuid.UUID(first["id"])) is not None
    assert db.get(Professor, uuid.UUID(second["id"])) is None


def _person_with_references(db: Session, email: str, old_id: uuid.UUID) -> tuple[User, Activity]:
    """A stored professor, a user account and an activity that all point at the old id."""
    upsert_professors(db, [{"id": str(old_id), "name": "Old", "email": email}], LoadReport())
    user = User(email=f"acct-{uuid.uuid4().hex[:8]}@ulbsibiu.ro", name="Prof", role=Role.PROFESSOR,
                professor_id=old_id)
    room = Classroom(name=f"R{uuid.uuid4().hex[:6]}", capacity=10)
    db.add_all([user, room])
    db.flush()
    activity = Activity(
        name="Didactic Activity", type=ActivityType.COURSE, priority=Priority.COURSE, classroom_id=room.id,
        day_of_week=2, start_time=time(8, 0), end_time=time(10, 0), professor_id=old_id,
    )
    db.add(activity)
    db.flush()
    return user, activity


def test_a_full_run_moves_the_row_and_its_references_to_the_new_id(db: Session) -> None:
    old_id = uuid.uuid4()
    new_id = str(uuid.uuid4())
    email = f"moved-{uuid.uuid4().hex[:8]}@ulbsibiu.ro"
    user, activity = _person_with_references(db, email, old_id)
    docs = [("ing.json", {"professors": [{"id": new_id, "name": "New Name", "email": email}]})]

    report = LoadReport()
    sync_professors(db, docs, full_run=True, report=report)

    assert report.rekeyed == [(str(old_id), new_id)]
    assert db.get(Professor, old_id) is None
    moved = db.get(Professor, uuid.UUID(new_id))
    assert moved.email == email and moved.name == "New Name"
    db.refresh(user)
    db.refresh(activity)
    assert user.professor_id == uuid.UUID(new_id)
    assert activity.professor_id == uuid.UUID(new_id)


def test_a_partial_run_does_not_move_rows_and_reports_the_refusal(db: Session) -> None:
    old_id = uuid.uuid4()
    new_id = str(uuid.uuid4())
    email = f"partial-{uuid.uuid4().hex[:8]}@ulbsibiu.ro"
    _person_with_references(db, email, old_id)
    docs = [("ing.json", {"professors": [{"id": new_id, "name": "New Name", "email": email}]})]

    report = LoadReport()
    sync_professors(db, docs, full_run=False, report=report)

    assert report.rekeyed == []
    assert report.email_conflicts == [new_id]
    assert db.get(Professor, old_id) is not None
