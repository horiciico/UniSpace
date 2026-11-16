"""Google sign-in ("bouncer") tests. Google is mocked; the database is real (see conftest.py)."""
from collections.abc import Iterator

import pytest
from authlib.integrations.base_client import OAuthError
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import oauth
from app.config import GOOGLE_REDIRECT_URI, POST_LOGIN_URL
from app.db import get_db
from app.main import app
from app.models import Invitation, Role, User

DENIED = "Access denied. Please use your institutional @ulbsibiu.ro account or request an invitation."


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    # https so the session cookie is sent back whatever COOKIE_SECURE is set to
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.clear()


def google_returns(monkeypatch: pytest.MonkeyPatch, **claims) -> None:
    payload = {"sub": "sub-1", "email": "ana@ulbsibiu.ro", "email_verified": True,
               "hd": "ulbsibiu.ro", "name": "Ana Pop"}
    payload.update(claims)
    payload = {k: v for k, v in payload.items() if v is not None}

    async def fake(request):
        return {"userinfo": payload}

    monkeypatch.setattr(oauth.google, "authorize_access_token", fake)


def callback(client: TestClient):
    return client.get("/auth/callback", follow_redirects=False)


def users(db: Session, email: str) -> list[User]:
    return list(db.scalars(select(User).where(User.email == email)))


def test_login_redirects_to_google(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    async def fake(request, redirect_uri, **kw):
        seen["uri"] = redirect_uri
        return RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth")

    monkeypatch.setattr(oauth.google, "authorize_redirect", fake)
    r = client.get("/auth/login", follow_redirects=False)

    assert r.status_code in (302, 307)
    assert seen["uri"] == GOOGLE_REDIRECT_URI


def test_google_error_is_a_400(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(request):
        raise OAuthError(error="access_denied")

    monkeypatch.setattr(oauth.google, "authorize_access_token", boom)
    assert callback(client).status_code == 400


def test_unverified_email_is_forbidden(client, db, monkeypatch) -> None:
    google_returns(monkeypatch, email_verified=False)
    assert callback(client).status_code == 403
    assert users(db, "ana@ulbsibiu.ro") == []


def test_university_user_is_provisioned_as_student(client, db, monkeypatch) -> None:
    google_returns(monkeypatch)
    r = callback(client)

    assert r.status_code == 303
    assert r.headers["location"] == POST_LOGIN_URL
    [user] = users(db, "ana@ulbsibiu.ro")
    assert (user.role, user.google_sub, user.name) == (Role.STUDENT, "sub-1", "Ana Pop")
    assert client.get("/auth/me").json()["email"] == "ana@ulbsibiu.ro"


def test_session_cookie_flags(client, db, monkeypatch) -> None:
    google_returns(monkeypatch)
    cookie = callback(client).headers["set-cookie"].lower()

    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "max-age=28800" in cookie


def test_second_login_does_not_duplicate(client, db, monkeypatch) -> None:
    google_returns(monkeypatch)
    callback(client)
    callback(client)
    assert db.scalar(select(func.count()).select_from(User)) == 1


def test_university_hd_with_foreign_email_is_forbidden(client, db, monkeypatch) -> None:
    google_returns(monkeypatch, email="ana@gmail.com", hd="ulbsibiu.ro")
    r = callback(client)
    assert r.status_code == 403
    assert users(db, "ana@gmail.com") == []


def test_university_email_without_hd_needs_an_invitation(client, db, monkeypatch) -> None:
    google_returns(monkeypatch, hd=None)
    r = callback(client)
    assert r.status_code == 403
    assert r.json()["detail"] == DENIED


def test_existing_university_row_is_linked(client, db, monkeypatch) -> None:
    db.add(User(email="ana@ulbsibiu.ro", name="Seeded", role=Role.PROFESSOR))
    db.commit()
    google_returns(monkeypatch)
    callback(client)

    [user] = users(db, "ana@ulbsibiu.ro")
    assert user.google_sub == "sub-1"
    assert user.role == Role.PROFESSOR  # linking never changes the role


def test_existing_row_with_other_sub_is_forbidden(client, db, monkeypatch) -> None:
    db.add(User(email="ana@ulbsibiu.ro", name="A", role=Role.STUDENT, google_sub="other"))
    db.commit()
    google_returns(monkeypatch)
    assert callback(client).status_code == 403


def test_known_external_sub_logs_in(client, db, monkeypatch) -> None:
    db.add(User(email="bob@gmail.com", name="Bob", role=Role.STUDENT_ORG, google_sub="sub-9"))
    db.commit()
    google_returns(monkeypatch, sub="sub-9", email="bob@gmail.com", hd=None, name="Bob")
    assert callback(client).status_code == 303
    assert client.get("/auth/me").json()["role"] == "STUDENT_ORG"


def test_invitation_creates_user_and_is_consumed_once(client, db, monkeypatch) -> None:
    db.add(Invitation(email="bob@gmail.com", role=Role.STUDENT_ORG))
    db.commit()
    google_returns(monkeypatch, sub="sub-9", email="Bob@Gmail.com", hd=None, name="Bob")

    assert callback(client).status_code == 303
    [user] = users(db, "bob@gmail.com")
    assert (user.role, user.google_sub) == (Role.STUDENT_ORG, "sub-9")
    assert db.scalar(select(Invitation.is_used)) is True

    # a different Google account with the same email cannot reuse it
    google_returns(monkeypatch, sub="sub-10", email="bob@gmail.com", hd=None)
    r = callback(client)
    assert r.status_code == 403
    assert r.json()["detail"] == DENIED


def test_stranger_is_rejected_with_message(client, db, monkeypatch) -> None:
    google_returns(monkeypatch, sub="sub-7", email="eve@gmail.com", hd=None)
    r = callback(client)
    assert r.status_code == 403
    assert r.json()["detail"] == DENIED
    assert users(db, "eve@gmail.com") == []


def test_invitation_does_not_clash_with_existing_email(client, db, monkeypatch) -> None:
    db.add_all([User(email="bob@gmail.com", name="B", role=Role.STUDENT),
                Invitation(email="bob@gmail.com", role=Role.ADMIN)])
    db.commit()
    google_returns(monkeypatch, sub="sub-9", email="bob@gmail.com", hd=None)

    assert callback(client).status_code == 403
    assert db.scalar(select(Invitation.is_used)) is False  # rolled back, not consumed


def test_university_user_ignores_invitation_for_now(client, db, monkeypatch) -> None:
    """Q-009, option A: every @ulbsibiu.ro user is a STUDENT; elevation is an admin action."""
    db.add(Invitation(email="ana@ulbsibiu.ro", role=Role.PROFESSOR))
    db.commit()
    google_returns(monkeypatch)
    callback(client)

    [user] = users(db, "ana@ulbsibiu.ro")
    assert user.role == Role.STUDENT
    assert db.scalar(select(Invitation.is_used)) is False


def test_me_requires_a_session_and_logout_ends_it(client, db, monkeypatch) -> None:
    assert client.get("/auth/me").status_code == 401

    google_returns(monkeypatch)
    callback(client)
    assert client.get("/auth/me").status_code == 200

    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401


def sign_in(client, db, monkeypatch, role: Role) -> None:
    db.add(User(email="who@gmail.com", name="Who", role=role, google_sub="sub-w"))
    db.commit()
    google_returns(monkeypatch, sub="sub-w", email="who@gmail.com", hd=None, name="Who")
    callback(client)


def test_admin_check_is_401_when_signed_out(client) -> None:
    assert client.get("/auth/admin").status_code == 401


def test_admin_check_is_403_for_other_roles(client, db, monkeypatch) -> None:
    sign_in(client, db, monkeypatch, Role.PROFESSOR)
    assert client.get("/auth/admin").status_code == 403


def test_admin_check_is_204_for_admin(client, db, monkeypatch) -> None:
    sign_in(client, db, monkeypatch, Role.ADMIN)
    assert client.get("/auth/admin").status_code == 204
