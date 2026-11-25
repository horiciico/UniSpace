"""Invitation sign-in (D-025): a valid invitation admits a new account with its role.

Google is mocked; the database is real (conftest.py). The invite token travels as
/login?invite=<token> -> /auth/login (kept in the session) -> the Google callback (consumed).
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import oauth
from app.db import get_db
from app.main import app
from app.models import InvitationStatus, Professor, Role, User, UserInvitation

DENIED = (
    "Access denied. Login is restricted to @ulbsibiu.ro accounts or registered faculty members."
)


@pytest.fixture
def client(db: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db

    async def fake_redirect(request, redirect_uri, **kw):
        return RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth")

    monkeypatch.setattr(oauth.google, "authorize_redirect", fake_redirect)
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.clear()


def google_returns(monkeypatch: pytest.MonkeyPatch, **claims) -> None:
    payload = {
        "sub": f"sub-{uuid.uuid4().hex}",
        "email": "ana@ulbsibiu.ro",
        "email_verified": True,
        "hd": "ulbsibiu.ro",
        "name": "Test",
    }
    payload.update(claims)
    payload = {k: v for k, v in payload.items() if v is not None}

    async def fake(request):
        return {"userinfo": payload}

    monkeypatch.setattr(oauth.google, "authorize_access_token", fake)


def sign_in_with_invite(client: TestClient, token: str | None = None):
    """Start the login as the login page does, then finish the Google callback."""
    if token is not None:
        client.get(f"/auth/login?invite={token}", follow_redirects=False)
    return client.get("/auth/callback", follow_redirects=False)


def invite(db: Session, email: str, role: Role, **fields) -> UserInvitation:
    values = {
        "email": email,
        "role": role,
        "token": uuid.uuid4().hex,
        "status": InvitationStatus.PENDING,
    }
    values.update(fields)
    row = UserInvitation(**values)
    db.add(row)
    db.flush()
    return row


def user_for(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def test_invited_external_account_gets_the_invited_role(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = invite(db, "reps@club.ro", Role.STUDENT_ORG)
    google_returns(monkeypatch, email="Reps@Club.ro", hd=None, name="Reps")

    r = sign_in_with_invite(client, row.token)

    assert r.status_code == 303
    user = user_for(db, "reps@club.ro")
    assert user is not None
    assert user.role == Role.STUDENT_ORG
    assert user.role_set_by_admin is True
    db.refresh(row)
    assert row.status == InvitationStatus.ACCEPTED


def test_invited_university_address_gets_the_invited_role(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = invite(db, "ion@ulbsibiu.ro", Role.PROFESSOR)
    google_returns(monkeypatch, email="ion@ulbsibiu.ro", name="Ion")

    sign_in_with_invite(client, row.token)

    assert user_for(db, "ion@ulbsibiu.ro").role == Role.PROFESSOR


def test_professor_list_wins_over_an_invitation(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    db.add(Professor(id=uuid.uuid4(), email="prof@gmail.com", name="Prof"))
    db.flush()
    row = invite(db, "prof@gmail.com", Role.STUDENT_ORG)
    google_returns(monkeypatch, email="prof@gmail.com", hd=None, name="Prof")

    sign_in_with_invite(client, row.token)

    assert user_for(db, "prof@gmail.com").role == Role.PROFESSOR
    db.refresh(row)
    assert row.status == InvitationStatus.PENDING


def test_a_token_for_another_email_does_not_admit(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = invite(db, "reps@club.ro", Role.STUDENT_ORG)
    google_returns(monkeypatch, email="eve@gmail.com", hd=None, name="Eve")

    r = sign_in_with_invite(client, row.token)

    assert r.status_code == 403
    assert user_for(db, "eve@gmail.com") is None
    db.refresh(row)
    assert row.status == InvitationStatus.PENDING


@pytest.mark.parametrize(
    "fields",
    [
        {"expires_at": datetime.now(UTC) - timedelta(seconds=1)},
        {"status": InvitationStatus.REVOKED},
        {"status": InvitationStatus.ACCEPTED},
    ],
)
def test_an_expired_revoked_or_used_invitation_does_not_admit(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch, fields: dict
) -> None:
    row = invite(db, "reps@club.ro", Role.STUDENT_ORG, **fields)
    google_returns(monkeypatch, email="reps@club.ro", hd=None, name="Reps")

    assert sign_in_with_invite(client, row.token).status_code == 403
    assert user_for(db, "reps@club.ro") is None


def test_an_existing_account_is_not_changed_by_an_invitation(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    db.add(User(email="ana@ulbsibiu.ro", name="Ana", role=Role.STUDENT))
    db.flush()
    row = invite(db, "ana@ulbsibiu.ro", Role.PROFESSOR)
    google_returns(monkeypatch, email="ana@ulbsibiu.ro")

    sign_in_with_invite(client, row.token)

    assert user_for(db, "ana@ulbsibiu.ro").role == Role.STUDENT
    db.refresh(row)
    assert row.status == InvitationStatus.PENDING


def test_an_admin_set_role_survives_the_next_sign_in(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    db.add(
        User(
            email="ana@ulbsibiu.ro",
            name="Ana",
            role=Role.PROFESSOR,
            role_set_by_admin=True,
        )
    )
    db.flush()
    google_returns(monkeypatch, email="ana@ulbsibiu.ro")

    sign_in_with_invite(client, None)

    assert user_for(db, "ana@ulbsibiu.ro").role == Role.PROFESSOR


def test_without_an_admin_set_role_a_university_sign_in_still_resets_to_student(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    db.add(User(email="ana@ulbsibiu.ro", name="Ana", role=Role.PROFESSOR))
    db.flush()
    google_returns(monkeypatch, email="ana@ulbsibiu.ro")

    sign_in_with_invite(client, None)

    assert user_for(db, "ana@ulbsibiu.ro").role == Role.STUDENT
