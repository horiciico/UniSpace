"""Current planning units query against PostgreSQL. Runs in the etl image (needs DATABASE_URL).

Each test rolls back its own writes, the same way backend/tests/conftest.py does.
"""
from collections.abc import Iterator
from datetime import date

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.db import engine
from app.models import Faculty, PlanningTimeUnit, PlanningUnitType
from etl.schedule.download import load_current_units


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


def _unit(faculty: Faculty, external_id: int, current: bool) -> PlanningTimeUnit:
    return PlanningTimeUnit(
        faculty_id=faculty.id, external_id=external_id, year=2026, name=f"Modul {external_id}",
        type=PlanningUnitType.MODULE, start_date=date(2026, 9, 30), end_date=date(2026, 11, 30),
        is_current=current,
    )


def test_only_current_units_are_loaded_with_their_faculty_code(db: Session) -> None:
    faculty = Faculty(code="tst5", name="Test")
    db.add(faculty)
    db.flush()
    db.add_all([_unit(faculty, 12, current=True), _unit(faculty, 13, current=False)])
    db.flush()

    units = load_current_units(db, "tst5")

    assert len(units) == 1
    assert units[0].faculty_code == "tst5"
    assert units[0].external_id == 12
    assert units[0].type == "module"
    assert units[0].start_date == date(2026, 9, 30)
    assert units[0].end_date == date(2026, 11, 30)


def test_faculty_filter_excludes_other_faculties(db: Session) -> None:
    faculty = Faculty(code="tst6", name="Test")
    other = Faculty(code="tst7", name="Test 2")
    db.add_all([faculty, other])
    db.flush()
    db.add_all([_unit(faculty, 1, current=True), _unit(other, 2, current=True)])
    db.flush()

    assert [u.faculty_code for u in load_current_units(db, "tst6")] == ["tst6"]
    assert {u.faculty_code for u in load_current_units(db)} >= {"tst6", "tst7"}
