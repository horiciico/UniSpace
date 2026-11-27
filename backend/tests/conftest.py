"""Shared fixtures. DB tests run the real Alembic migration, then roll every test back."""

from collections.abc import Iterator

import pytest
from alembic.config import Config
from sqlalchemy import delete
from sqlalchemy.orm import Session

from alembic import command
from app import config
from app.db import engine
from app.models import AcademicPeriod


@pytest.fixture(autouse=True)
def console_email(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never send real email, whatever .env says: the console backend is used."""
    monkeypatch.setattr(config, "EMAIL_BACKEND", "console")


@pytest.fixture(scope="session")
def migrated() -> None:
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")


@pytest.fixture
def db(migrated: None) -> Iterator[Session]:
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    # Periods an admin set in this database would change what every dated test sees. They are
    # removed inside the outer transaction only, so the rollback below brings them back.
    session.execute(delete(AcademicPeriod))
    session.commit()
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()
