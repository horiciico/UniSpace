"""Faculty upsert against PostgreSQL. Runs in the etl image (needs DATABASE_URL).

Each test rolls back its own writes, the same way backend/tests/conftest.py does.
"""
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import Faculty
from etl.schedule.downloader import faculty_rows, upsert_faculties


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


def test_faculty_rows_map_api_id_to_code() -> None:
    payload = {"success": True, "data": [{"id": "dre", "name": "Facultatea de Drept", "dean": "x"}]}
    assert faculty_rows(payload) == [{"code": "dre", "name": "Facultatea de Drept"}]


def test_upsert_inserts_then_updates_without_duplicates(db: Session) -> None:
    first = {"data": [{"id": "tst", "name": "Nume vechi"}]}
    second = {"data": [{"id": "tst", "name": "Nume nou"}]}

    assert upsert_faculties(db, first) == ["tst"]
    assert upsert_faculties(db, second) == ["tst"]

    rows = db.scalars(select(Faculty).where(Faculty.code == "tst")).all()
    assert len(rows) == 1
    assert rows[0].name == "Nume nou"


def test_upsert_with_no_faculties_writes_nothing(db: Session) -> None:
    assert upsert_faculties(db, {"data": []}) == []
