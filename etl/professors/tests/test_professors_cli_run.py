"""Professors command line: what runs for each step, and what it prints. The steps are replaced; no network, no database
(except the faculty query, which runs against the test session)."""
import asyncio
import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.db import engine
from app.models import Faculty
from etl.professors import cli
from etl.professors.extract import ExtractResult
from etl.professors.load import LoadReport


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


def test_the_faculty_codes_come_from_the_faculties_table(db: Session, monkeypatch) -> None:
    code = f"t{uuid.uuid4().hex[:6]}"
    db.add(Faculty(code=code, name="Test"))
    db.flush()
    # Each call opens its own session on the test connection, so the closed session does not drop the rows.
    monkeypatch.setattr(cli, "SessionLocal", lambda: Session(bind=db.connection(), join_transaction_mode="create_savepoint"))

    assert code in cli._faculty_codes(None)
    assert cli._faculty_codes(code) == [code]
    assert cli._faculty_codes("no-such-faculty") == []


def test_no_faculties_stops_with_a_message(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "_faculty_codes", lambda faculty: [])
    asyncio.run(cli._main([]))
    assert "No faculty found" in capsys.readouterr().out


def test_extract_then_load_prints_both_results(monkeypatch, capsys) -> None:
    async def fake_extract(codes):
        return [
            ExtractResult("ing", "ok", stored=2, skipped=1, path="data/professors/ing.json"),
            ExtractResult("sti", "error", note="HTTP error: 500"),
        ]

    monkeypatch.setattr(cli, "_faculty_codes", lambda faculty: ["ing", "sti"])
    monkeypatch.setattr(cli, "extract_faculties", fake_extract)
    monkeypatch.setattr(
        cli, "load_professors",
        lambda faculty=None: LoadReport(files=["ing.json"], records=2, stored=2,
                                        warnings=["duplicate email: id a left out, id b kept"],
                                        errors=["bad.json: cannot read"], email_conflicts=["c"]),
    )

    asyncio.run(cli._main([]))

    out = capsys.readouterr().out
    assert "[ing] ok: 2 professors, 1 skipped -> data/professors/ing.json" in out
    assert "[sti] FAILED: HTTP error: 500" in out
    assert "warning: duplicate email" in out
    assert "error: bad.json: cannot read" in out
    assert "refused, id c" in out


def test_load_only_passes_the_faculty_and_does_not_extract(monkeypatch, capsys) -> None:
    seen = {}

    def fake_load(faculty=None):
        seen["faculty"] = faculty
        return LoadReport()

    async def no_extract(codes):
        raise AssertionError("extract must not run for --step load")

    monkeypatch.setattr(cli, "load_professors", fake_load)
    monkeypatch.setattr(cli, "extract_faculties", no_extract)

    asyncio.run(cli._main(["--step", "load", "--faculty", "ing"]))

    assert seen["faculty"] == "ing"
    assert "distinct professors: 0" in capsys.readouterr().out


def test_extract_only_does_not_load(monkeypatch, capsys) -> None:
    loads = []

    async def fake_extract(codes):
        return []

    monkeypatch.setattr(cli, "_faculty_codes", lambda faculty: ["ing"])
    monkeypatch.setattr(cli, "extract_faculties", fake_extract)
    monkeypatch.setattr(cli, "load_professors", lambda faculty=None: loads.append(1) or LoadReport())

    asyncio.run(cli._main(["--step", "extract"]))

    assert loads == []
