"""Professors load, the whole run against PostgreSQL (one commit; a database error is reported, not raised).

The run uses the test's own session (its writes are rolled back), in place of SessionLocal.
"""
import json
import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import engine
from app.models import Professor
from etl.professors import load
from etl.professors.load import load_professors


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


@pytest.fixture
def run_db(db: Session, monkeypatch: pytest.MonkeyPatch) -> Session:
    monkeypatch.setattr(load, "SessionLocal", lambda: db)
    return db


def write_faculty(folder, code: str, professors: list[dict]) -> None:
    (folder / f"{code}.json").write_text(json.dumps({"faculty_code": code, "professors": professors}), encoding="utf-8")


def test_a_run_stores_the_files_and_reads_them_back(run_db: Session, tmp_path) -> None:
    person = {"id": str(uuid.uuid4()), "name": "Run Test", "email": f"run-{uuid.uuid4().hex[:8]}@ulbsibiu.ro"}
    write_faculty(tmp_path, "ing", [person])

    report = load_professors(directory=tmp_path)

    assert report.files == ["ing.json"]
    assert report.errors == []
    assert report.stored == 1
    assert run_db.get(Professor, uuid.UUID(person["id"])).name == "Run Test"


def test_an_unreadable_file_is_reported_and_the_run_goes_on(run_db: Session, tmp_path) -> None:
    person = {"id": str(uuid.uuid4()), "name": "Still Loaded", "email": f"ok-{uuid.uuid4().hex[:8]}@ulbsibiu.ro"}
    write_faculty(tmp_path, "ing", [person])
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")

    report = load_professors(directory=tmp_path)

    assert report.stored == 1
    assert any(error.startswith("bad.json: cannot read") for error in report.errors)


def test_a_database_error_is_reported_not_raised(run_db: Session, tmp_path, monkeypatch) -> None:
    write_faculty(tmp_path, "ing", [{"id": str(uuid.uuid4()), "name": "X", "email": "x@ulbsibiu.ro"}])

    def broken(*args, **kwargs):
        raise SQLAlchemyError("connection lost")

    monkeypatch.setattr(load, "sync_professors", broken)

    report = load_professors(directory=tmp_path)

    assert report.stored == 0
    assert report.rekeyed == []
    assert any(error.startswith("database error: SQLAlchemyError") for error in report.errors)
