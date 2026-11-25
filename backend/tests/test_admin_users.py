"""Admin Users tab, backend (step 2): list and search users, change a role, invite and revoke.

Only an ADMIN may use these endpoints (403 for others, 401 signed out). An invitation for an
email that already has an account is refused with 409, naming the account's email and role.

DB tests: the endpoints run against the rolled-back `db` fixture (PATTERN-005, PATTERN-006).
"""

import logging
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import oauth
from app.db import get_db
from app.main import app
from app.models import InvitationStatus, Role, User, UserInvitation


@pytest.fixture(autouse=True)
def reset_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


def make_client(db: Session) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, base_url="https://testserver")


def sign_in(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    email: str,
    role: Role,
) -> User:
    claims = {
        "sub": f"sub-{uuid.uuid4().hex}",
        "email": email,
        "email_verified": True,
        "hd": "ulbsibiu.ro",
        "name": "Test",
    }

    async def fake(request):
        return {"userinfo": claims}

    monkeypatch.setattr(oauth.google, "authorize_access_token", fake)
    client.get("/auth/callback", follow_redirects=False)
    user = db.scalar(select(User).where(User.email == email))
    user.role = role
    db.flush()
    return user


def add_user(db: Session, email: str, role: Role = Role.STUDENT) -> User:
    user = User(email=email, name=email.split("@")[0], role=role)
    db.add(user)
    db.flush()
    return user


def add_invitation(db: Session, email: str, **fields) -> UserInvitation:
    values = {
        "email": email,
        "role": Role.STUDENT_ORG,
        "token": uuid.uuid4().hex,
        "status": InvitationStatus.PENDING,
    }
    values.update(fields)
    invitation = UserInvitation(**values)
    db.add(invitation)
    db.flush()
    return invitation


@pytest.fixture
def admin_client(db: Session, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "root@ulbsibiu.ro", Role.ADMIN)
    return client


@pytest.fixture
def tag() -> str:
    """A unique search term, so each test sees only its own rows."""
    return uuid.uuid4().hex[:10]


# --- access -----------------------------------------------------------------


@pytest.mark.parametrize("role", [Role.STUDENT, Role.PROFESSOR, Role.STUDENT_ORG])
def test_non_admins_get_403_on_every_endpoint(
    db: Session, monkeypatch: pytest.MonkeyPatch, role: Role
) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, f"{role.value.lower()}@ulbsibiu.ro", role)
    target = add_user(db, "target@ulbsibiu.ro")
    invitation = add_invitation(db, "invited@gmail.com")

    assert client.get("/api/admin/users").status_code == 403
    assert (
        client.patch(f"/api/admin/users/{target.id}/role", json={"role": "STUDENT_ORG"}).status_code
        == 403
    )
    assert client.get("/api/admin/invitations").status_code == 403
    assert (
        client.post(
            "/api/admin/invitations", json={"email": "new@gmail.com", "role": "STUDENT"}
        ).status_code
        == 403
    )
    assert client.delete(f"/api/admin/invitations/{invitation.id}").status_code == 403


def test_signed_out_gets_401(db: Session) -> None:
    client = make_client(db)
    assert client.get("/api/admin/users").status_code == 401
    assert client.get("/api/admin/invitations").status_code == 401


# --- list and search ----------------------------------------------------------


def test_list_filters_by_role_and_searches_email_ignoring_case(
    db: Session, admin_client: TestClient, tag: str
) -> None:
    add_user(db, f"ana.{tag}@ulbsibiu.ro", Role.STUDENT)
    add_user(db, f"ion.{tag}@ulbsibiu.ro", Role.PROFESSOR)

    found = admin_client.get("/api/admin/users", params={"search": tag.upper()}).json()
    assert found["total"] == 2
    assert {item["email"] for item in found["items"]} == {
        f"ana.{tag}@ulbsibiu.ro",
        f"ion.{tag}@ulbsibiu.ro",
    }

    only_professors = admin_client.get(
        "/api/admin/users", params={"search": tag, "role": "PROFESSOR"}
    ).json()
    assert only_professors["total"] == 1
    assert only_professors["items"][0]["email"] == f"ion.{tag}@ulbsibiu.ro"
    assert only_professors["items"][0]["role"] == "PROFESSOR"


def test_list_item_carries_name_and_group_fields(
    db: Session, admin_client: TestClient, tag: str
) -> None:
    add_user(db, f"ana.{tag}@ulbsibiu.ro", Role.STUDENT)

    [item] = admin_client.get("/api/admin/users", params={"search": tag}).json()["items"]
    assert set(item) == {
        "id",
        "email",
        "name",
        "role",
        "faculty_name",
        "study_formation_name",
        "created_at",
    }
    assert item["created_at"] is not None
    assert item["faculty_name"] is None
    assert item["study_formation_name"] is None


def test_list_pages_with_limit_and_offset(db: Session, admin_client: TestClient, tag: str) -> None:
    for n in range(3):
        add_user(db, f"u{n}.{tag}@ulbsibiu.ro")

    first = admin_client.get(
        "/api/admin/users", params={"search": tag, "limit": 2, "offset": 0}
    ).json()
    second = admin_client.get(
        "/api/admin/users", params={"search": tag, "limit": 2, "offset": 2}
    ).json()

    assert first["total"] == 3
    assert (first["limit"], first["offset"]) == (2, 0)
    assert len(first["items"]) == 2
    assert len(second["items"]) == 1
    assert admin_client.get("/api/admin/users", params={"limit": 201}).status_code == 422


def test_search_treats_percent_and_underscore_as_plain_text(
    db: Session, admin_client: TestClient, tag: str
) -> None:
    add_user(db, f"ana_{tag}@ulbsibiu.ro")
    add_user(db, f"anax{tag}@ulbsibiu.ro")

    found = admin_client.get("/api/admin/users", params={"search": f"ana_{tag}"}).json()
    assert [item["email"] for item in found["items"]] == [f"ana_{tag}@ulbsibiu.ro"]


# --- change a role ------------------------------------------------------------


def test_admin_changes_a_user_role_and_the_role_is_kept(
    db: Session, admin_client: TestClient
) -> None:
    target = add_user(db, "ion@ulbsibiu.ro", Role.STUDENT)

    r = admin_client.patch(f"/api/admin/users/{target.id}/role", json={"role": "PROFESSOR"})

    assert r.status_code == 200
    assert r.json()["role"] == "PROFESSOR"
    db.refresh(target)
    assert target.role == Role.PROFESSOR
    assert target.role_set_by_admin is True


def test_a_role_cannot_be_set_to_admin(db: Session, admin_client: TestClient) -> None:
    target = add_user(db, "ion@ulbsibiu.ro", Role.STUDENT)

    r = admin_client.patch(f"/api/admin/users/{target.id}/role", json={"role": "ADMIN"})

    assert r.status_code == 422
    db.refresh(target)
    assert target.role == Role.STUDENT


def test_an_admin_account_cannot_be_changed(db: Session, admin_client: TestClient) -> None:
    other_admin = add_user(db, "other-admin@ulbsibiu.ro", Role.ADMIN)

    r = admin_client.patch(f"/api/admin/users/{other_admin.id}/role", json={"role": "STUDENT"})

    assert r.status_code == 403
    db.refresh(other_admin)
    assert other_admin.role == Role.ADMIN


def test_unknown_user_is_404_and_unknown_role_is_422(db: Session, admin_client: TestClient) -> None:
    target = add_user(db, "ion@ulbsibiu.ro", Role.STUDENT)

    assert (
        admin_client.patch(
            f"/api/admin/users/{uuid.uuid4()}/role", json={"role": "STUDENT"}
        ).status_code
        == 404
    )
    assert (
        admin_client.patch(f"/api/admin/users/{target.id}/role", json={"role": "ROOT"}).status_code
        == 422
    )


# --- invitations --------------------------------------------------------------


def test_invitation_is_created_with_a_link_and_the_token_is_not_logged(
    db: Session, admin_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    r = admin_client.post(
        "/api/admin/invitations", json={"email": "Reps@Club.ro", "role": "STUDENT_ORG"}
    )

    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "reps@club.ro"
    assert body["role"] == "STUDENT_ORG"
    assert body["invite_url"] == f"/login?invite={body['token']}"
    assert body["expires_at"] is not None
    assert body["created_at"] is not None
    assert body["token"] not in caplog.text  # the link is not written to the log (AGENTS.md)

    row = db.scalar(select(UserInvitation).where(UserInvitation.token == body["token"]))
    assert row is not None
    assert row.status == InvitationStatus.PENDING
    assert row.invited_by is not None


def test_invitation_cannot_have_the_admin_role(admin_client: TestClient) -> None:
    r = admin_client.post(
        "/api/admin/invitations", json={"email": "root2@gmail.com", "role": "ADMIN"}
    )
    assert r.status_code == 422


def test_existing_user_gets_409_with_their_email_and_role(
    db: Session, admin_client: TestClient
) -> None:
    add_user(db, "ion@ulbsibiu.ro", Role.PROFESSOR)

    r = admin_client.post(
        "/api/admin/invitations", json={"email": "ION@ulbsibiu.ro", "role": "STUDENT"}
    )

    assert r.status_code == 409
    assert r.json()["detail"] == "User already exists"
    assert r.json()["existing_user"] == {"email": "ion@ulbsibiu.ro", "role": "PROFESSOR"}


def test_a_second_active_invitation_for_the_same_email_is_409(admin_client: TestClient) -> None:
    payload = {"email": "reps@club.ro", "role": "STUDENT_ORG"}
    assert admin_client.post("/api/admin/invitations", json=payload).status_code == 201
    assert admin_client.post("/api/admin/invitations", json=payload).status_code == 409


def test_an_expired_pending_invitation_is_revoked_when_reinvited(
    db: Session, admin_client: TestClient
) -> None:
    old = add_invitation(
        db,
        "reps@club.ro",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )

    r = admin_client.post(
        "/api/admin/invitations", json={"email": "reps@club.ro", "role": "STUDENT_ORG"}
    )

    assert r.status_code == 201
    db.refresh(old)
    assert old.status == InvitationStatus.REVOKED


def test_list_shows_only_active_pending_invitations_newest_first(
    db: Session, admin_client: TestClient
) -> None:
    now = datetime.now(UTC)
    older = add_invitation(db, "older@club.ro", created_at=now - timedelta(days=2))
    newer = add_invitation(db, "newer@club.ro", created_at=now - timedelta(days=1))
    add_invitation(db, "expired@club.ro", expires_at=now - timedelta(days=1))
    add_invitation(db, "revoked@club.ro", status=InvitationStatus.REVOKED)
    add_invitation(db, "used@club.ro", status=InvitationStatus.ACCEPTED)

    items = admin_client.get("/api/admin/invitations").json()

    assert [item["email"] for item in items] == [newer.email, older.email]
    assert {"id", "email", "role", "token", "invite_url", "expires_at", "created_at"} <= set(
        items[0]
    )
    assert items[0]["invite_url"] == f"/login?invite={newer.token}"


def test_revoke_marks_a_pending_invitation_and_only_once(
    db: Session, admin_client: TestClient
) -> None:
    invitation = add_invitation(db, "reps@club.ro")

    assert admin_client.delete(f"/api/admin/invitations/{invitation.id}").status_code == 204
    db.refresh(invitation)
    assert invitation.status == InvitationStatus.REVOKED
    assert admin_client.delete(f"/api/admin/invitations/{invitation.id}").status_code == 409
    assert admin_client.delete(f"/api/admin/invitations/{uuid.uuid4()}").status_code == 404
