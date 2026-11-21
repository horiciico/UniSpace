"""Planning-unit upsert against PostgreSQL. Runs in the etl image (needs DATABASE_URL).

Each test rolls back its own writes, the same way backend/tests/conftest.py does.
"""
from collections.abc import Iterator
from datetime import date

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import Faculty, PlanningTimeUnit
from etl.downloader import ActiveUnit, upsert_planning_unit


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


def _unit(external_id: int, name: str, start: str, end: str, current: bool = True) -> dict:
    return {
        "id": external_id, "year": 2026, "name": name, "type": "module", "startDate": start,
        "endDate": end, "displayName": f"{name} 2026", "isCurrent": current,
    }


def test_upsert_is_idempotent_and_updates_the_row(db: Session) -> None:
    faculty = Faculty(code="tst", name="Test")
    db.add(faculty)
    db.flush()

    upsert_planning_unit(db, faculty.id, ActiveUnit("module", _unit(12, "Modul 1", "2026-09-30", "2026-11-30")))
    upsert_planning_unit(db, faculty.id, ActiveUnit("module", _unit(12, "Modul 1 nou", "2026-09-30", "2026-12-15")))

    rows = db.scalars(select(PlanningTimeUnit).where(PlanningTimeUnit.faculty_id == faculty.id)).all()
    assert len(rows) == 1
    assert rows[0].external_id == 12
    assert rows[0].name == "Modul 1 nou"
    assert rows[0].end_date == date(2026, 12, 15)
    assert rows[0].is_current is True


def test_only_one_unit_per_faculty_is_current(db: Session) -> None:
    faculty = Faculty(code="tst2", name="Test")
    db.add(faculty)
    db.flush()

    upsert_planning_unit(db, faculty.id, ActiveUnit("module", _unit(12, "Modul 1", "2026-09-30", "2026-11-30")))
    upsert_planning_unit(db, faculty.id, ActiveUnit("module", _unit(13, "Modul 2", "2026-12-02", "2027-02-28")))

    units = {u.external_id: u for u in db.scalars(
        select(PlanningTimeUnit).where(PlanningTimeUnit.faculty_id == faculty.id)
    ).all()}
    assert units[12].is_current is False
    assert units[13].is_current is True


def test_bad_dates_are_rejected_before_writing(db: Session) -> None:
    faculty = Faculty(code="tst3", name="Test")
    db.add(faculty)
    db.flush()
    broken = {"id": 9, "year": 2026, "name": "X", "type": "module", "isCurrent": True}
    with pytest.raises(ValueError):
        upsert_planning_unit(db, faculty.id, ActiveUnit("module", broken))
