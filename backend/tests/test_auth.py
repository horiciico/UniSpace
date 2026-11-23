"""Google sign-in ("bouncer") tests. Google is mocked; the database is real (see conftest.py)."""
import uuid
from collections.abc import Iterator

import pytest
from authlib.integrations.base_client import OAuthError
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import config
from app.auth import oauth
from app.config import GOOGLE_REDIRECT_URI, POST_LOGIN_URL
from app.db import get_db
from app.main import app
from app.models import Invitation, Professor, Role, User

DENIED = "Access denied. Login is restricted to @ulbsibiu.ro accounts or registered faculty members."


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


def test_google_login_saves_and_returns_picture(client, db, monkeypatch) -> None:
    google_returns(monkeypatch, picture="https://lh3.googleusercontent.com/photo.jpg")
    r = callback(client)
    assert r.status_code == 303
    me = client.get("/auth/me").json()
    assert me["picture"] == "https://lh3.googleusercontent.com/photo.jpg"


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
    # Count only this test's account: the database may hold other users (a real sign-in, seeded data).
    assert len(users(db, "ana@ulbsibiu.ro")) == 1


def test_university_hd_with_foreign_email_is_forbidden(client, db, monkeypatch) -> None:
    google_returns(monkeypatch, email="ana@gmail.com", hd="ulbsibiu.ro")
    r = callback(client)
    assert r.status_code == 403
    assert users(db, "ana@gmail.com") == []


def test_university_email_without_hd_is_rejected(client, db, monkeypatch) -> None:
    google_returns(monkeypatch, hd=None)
    r = callback(client)
    assert r.status_code == 403
    assert r.json()["detail"] == DENIED


def test_existing_university_row_is_linked_and_role_resolved(client, db, monkeypatch) -> None:
    db.add(User(email="ana@ulbsibiu.ro", name="Seeded", role=Role.PROFESSOR))
    db.commit()
    google_returns(monkeypatch)
    callback(client)

    [user] = users(db, "ana@ulbsibiu.ro")
    assert user.google_sub == "sub-1"
    assert user.role == Role.STUDENT  # D-020: not in the professor list, so the role is resolved again


def test_existing_row_with_other_sub_is_forbidden(client, db, monkeypatch) -> None:
    db.add(User(email="ana@ulbsibiu.ro", name="A", role=Role.STUDENT, google_sub="other"))
    db.commit()
    google_returns(monkeypatch)
    assert callback(client).status_code == 403


def test_known_external_sub_is_rejected_unless_listed_as_professor(client, db, monkeypatch) -> None:
    db.add(User(email="bob@gmail.com", name="Bob", role=Role.STUDENT_ORG, google_sub="sub-9"))
    db.commit()
    google_returns(monkeypatch, sub="sub-9", email="bob@gmail.com", hd=None, name="Bob")
    assert callback(client).status_code == 403


def test_invitation_no_longer_admits_an_external_address(client, db, monkeypatch) -> None:
    db.add(Invitation(email="bob@gmail.com", role=Role.STUDENT_ORG))
    db.commit()
    google_returns(monkeypatch, sub="sub-9", email="Bob@Gmail.com", hd=None, name="Bob")

    r = callback(client)
    assert r.status_code == 403
    assert r.json()["detail"] == DENIED
    assert users(db, "bob@gmail.com") == []
    assert db.scalar(select(Invitation.is_used)) is False


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
    db.add(User(email="who@ulbsibiu.ro", name="Who", role=role, google_sub="sub-w"))
    db.commit()
    google_returns(monkeypatch, sub="sub-w", email="who@ulbsibiu.ro", name="Who")
    callback(client)


def test_admin_check_is_401_when_signed_out(client) -> None:
    assert client.get("/auth/admin").status_code == 401


def test_admin_check_is_403_for_other_roles(client, db, monkeypatch) -> None:
    sign_in(client, db, monkeypatch, Role.PROFESSOR)
    assert client.get("/auth/admin").status_code == 403


def test_admin_check_is_204_for_admin(client, db, monkeypatch) -> None:
    sign_in(client, db, monkeypatch, Role.ADMIN)
    assert client.get("/auth/admin").status_code == 204


# --- D-020: role on every sign-in ---------------------------------------------------------

def add_professor(db: Session, email: str) -> Professor:
    professor = Professor(id=uuid.uuid4(), name="Prof Test", email=email)
    db.add(professor)
    db.commit()
    return professor


def test_professor_on_a_university_address_gets_the_role_and_id(client, db, monkeypatch) -> None:
    professor = add_professor(db, "ana.prof@ulbsibiu.ro")
    google_returns(monkeypatch, email="ana.prof@ulbsibiu.ro")
    assert callback(client).status_code == 303

    [user] = users(db, "ana.prof@ulbsibiu.ro")
    assert (user.role, user.professor_id) == (Role.PROFESSOR, professor.id)


def test_external_professor_can_sign_in_with_the_role_and_id(client, db, monkeypatch) -> None:
    professor = add_professor(db, "guest.prof@gmail.com")
    google_returns(monkeypatch, sub="sub-g", email="guest.prof@gmail.com", hd=None, name="Guest")

    assert callback(client).status_code == 303
    [user] = users(db, "guest.prof@gmail.com")
    assert (user.role, user.professor_id) == (Role.PROFESSOR, professor.id)
    assert client.get("/auth/me").json()["role"] == "PROFESSOR"


def test_email_is_normalized_before_the_professor_lookup(client, db, monkeypatch) -> None:
    professor = add_professor(db, "norm.prof@ulbsibiu.ro")
    google_returns(monkeypatch, email="  Norm.Prof@ULBSibiu.ro ")
    callback(client)

    [user] = users(db, "norm.prof@ulbsibiu.ro")
    assert user.professor_id == professor.id


def test_non_professor_university_user_has_no_professor_id(client, db, monkeypatch) -> None:
    google_returns(monkeypatch, email="plain.student@ulbsibiu.ro")
    callback(client)
    [user] = users(db, "plain.student@ulbsibiu.ro")
    assert (user.role, user.professor_id) == (Role.STUDENT, None)


def test_non_professor_external_address_is_forbidden(client, db, monkeypatch) -> None:
    google_returns(monkeypatch, sub="sub-e", email="eve.stranger@gmail.com", hd=None)
    assert callback(client).status_code == 403
    assert users(db, "eve.stranger@gmail.com") == []


def test_former_professor_on_a_university_address_goes_back_to_student(client, db, monkeypatch) -> None:
    db.add(User(email="left@ulbsibiu.ro", name="Left", role=Role.PROFESSOR, google_sub="sub-l",
                professor_id=uuid.uuid4()))
    db.commit()
    google_returns(monkeypatch, sub="sub-l", email="left@ulbsibiu.ro", name="Left")
    assert callback(client).status_code == 303

    [user] = users(db, "left@ulbsibiu.ro")
    assert (user.role, user.professor_id) == (Role.STUDENT, None)


def test_former_professor_on_an_external_address_is_rejected(client, db, monkeypatch) -> None:
    db.add(User(email="gone@gmail.com", name="Gone", role=Role.PROFESSOR, google_sub="sub-gone"))
    db.commit()
    google_returns(monkeypatch, sub="sub-gone", email="gone@gmail.com", hd=None, name="Gone")
    assert callback(client).status_code == 403


def test_admin_is_not_lowered_by_a_university_login(client, db, monkeypatch) -> None:
    db.add(User(email="boss@ulbsibiu.ro", name="Boss", role=Role.ADMIN, google_sub="sub-b"))
    db.commit()
    google_returns(monkeypatch, sub="sub-b", email="boss@ulbsibiu.ro", name="Boss")
    callback(client)
    [user] = users(db, "boss@ulbsibiu.ro")
    assert user.role == Role.ADMIN


def test_student_org_is_not_lowered_by_a_university_login(client, db, monkeypatch) -> None:
    db.add(User(email="club@ulbsibiu.ro", name="Club", role=Role.STUDENT_ORG, google_sub="sub-c"))
    db.commit()
    google_returns(monkeypatch, sub="sub-c", email="club@ulbsibiu.ro", name="Club")
    callback(client)
    [user] = users(db, "club@ulbsibiu.ro")
    assert user.role == Role.STUDENT_ORG


def test_student_association_hook_is_checked_before_the_student_tier(client, db, monkeypatch) -> None:
    monkeypatch.setattr("app.auth.is_student_association", lambda email: True)
    google_returns(monkeypatch, email="club.lead@ulbsibiu.ro")
    callback(client)
    [user] = users(db, "club.lead@ulbsibiu.ro")
    assert user.role == Role.STUDENT_ORG


def test_the_default_association_hook_admits_nobody() -> None:
    from app.auth import is_student_association
    assert is_student_association("anyone@ulbsibiu.ro") is False


# --- D-021: admin sign-in with the .env credentials ---------------------------------------

@pytest.fixture
def admin_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "ADMIN_USERNAME", "uni-admin")
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "s3cret-test-value")


def admin_login(client: TestClient, username: str = "uni-admin", password: str = "s3cret-test-value"):
    return client.post("/auth/admin-login", json={"username": username, "password": password})


def test_admin_login_with_the_right_credentials_gives_a_session(client, db, admin_env) -> None:
    r = admin_login(client)

    assert r.status_code == 200
    assert r.json()["role"] == "ADMIN"
    assert "httponly" in r.headers["set-cookie"].lower()
    assert client.get("/auth/me").json()["role"] == "ADMIN"
    assert client.get("/auth/admin").status_code == 204
    [user] = users(db, "uni-admin")
    assert user.role == Role.ADMIN and user.google_sub is None


def test_admin_login_twice_does_not_duplicate_the_row(client, db, admin_env) -> None:
    admin_login(client)
    admin_login(client)
    assert len(users(db, "uni-admin")) == 1


def test_wrong_password_is_401(client, db, admin_env) -> None:
    r = admin_login(client, password="wrong")
    assert r.status_code == 401
    assert client.get("/auth/me").status_code == 401


def test_wrong_username_is_401(client, db, admin_env) -> None:
    assert admin_login(client, username="someone-else").status_code == 401


def test_admin_login_is_off_when_the_credentials_are_not_set(client, db, monkeypatch) -> None:
    monkeypatch.setattr(config, "ADMIN_USERNAME", "")
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "")
    assert admin_login(client, username="", password="").status_code == 401


def test_admin_login_needs_both_fields(client, db, admin_env) -> None:
    assert client.post("/auth/admin-login", json={"username": "uni-admin"}).status_code == 422
