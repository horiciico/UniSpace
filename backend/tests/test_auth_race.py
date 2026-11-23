"""Sign-in when the database refuses the write: a concurrent callback created the account first (D-020).
Google is mocked; the database is real (see conftest.py)."""
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import oauth
from app.db import get_db
from app.main import app
from app.models import User

DENIED = "Access denied. Login is restricted to @ulbsibiu.ro accounts or registered faculty members."


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.clear()


def test_a_refused_write_is_a_403_and_the_session_stays_usable(client, db, monkeypatch) -> None:
    claims = {"sub": "sub-race", "email": "race@ulbsibiu.ro", "email_verified": True,
              "hd": "ulbsibiu.ro", "name": "Race"}

    async def fake(request):
        return {"userinfo": claims}

    monkeypatch.setattr(oauth.google, "authorize_access_token", fake)

    def refused():
        raise IntegrityError("INSERT users", {}, Exception("duplicate key"))

    monkeypatch.setattr(db, "commit", refused)

    r = client.get("/auth/callback", follow_redirects=False)

    assert r.status_code == 403
    assert r.json()["detail"] == DENIED
    monkeypatch.undo()
    assert db.scalar(select(User).where(User.email == "race@ulbsibiu.ro")) is None  # nothing was saved
