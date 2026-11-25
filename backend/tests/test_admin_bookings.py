"""Issue #23: an admin reviews pending booking requests and accepts or rejects them.

GET /api/admin/bookings/pending lists pending requests with requester name, email and role.
POST /api/admin/bookings/{id}/decision approves or rejects one, with an optional message.
Only an admin may do either. A decision records who made it and when; the requester sees it.

DB tests: the endpoints run against the rolled-back `db` fixture (PATTERN-005, PATTERN-006).
"""

import uuid
from collections.abc import Iterator
from datetime import date, datetime, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import oauth
from app.db import get_db
from app.main import app
from app.models import Booking, BookingStatus, Classroom, Role, User
from app.planning import LOCAL_TZ

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=LOCAL_TZ)
DAY = "2026-12-14"


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.routers.bookings.local_now", lambda: NOW)


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
    sub: str,
    email: str,
    role: Role = Role.STUDENT,
) -> User:
    claims = {
        "sub": sub,
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


@pytest.fixture
def room(db: Session) -> Classroom:
    tag = uuid.uuid4().hex[:8]
    room = Classroom(name=f"R-{tag}", capacity=30, external_id=f"r-{tag}")
    db.add(room)
    db.flush()
    return room


def booking(db: Session, user: User, room: Classroom, **kw) -> Booking:
    values = dict(
        user_id=user.id,
        classroom_id=room.id,
        specific_date=date(2026, 12, 14),
        start_time=time(13, 0),
        end_time=time(14, 30),
        title="Club",
    )
    values.update(kw)
    row = Booking(**values)
    db.add(row)
    db.flush()
    return row


def test_only_an_admin_can_see_the_pending_requests(db, room, monkeypatch) -> None:
    student = make_client(db)
    sign_in(db, student, monkeypatch, "sub-a1", "review.student@ulbsibiu.ro")
    assert student.get("/api/admin/bookings/pending").status_code == 403
    assert make_client(db).get("/api/admin/bookings/pending").status_code == 401


def test_the_pending_list_shows_each_requester_and_role(db, room, monkeypatch) -> None:
    admin = make_client(db)
    sign_in(db, admin, monkeypatch, "sub-a2", "review.admin@ulbsibiu.ro", role=Role.ADMIN)
    org = User(email="org@ulbsibiu.ro", name="Clubul de robotica", role=Role.STUDENT_ORG)
    db.add(org)
    db.flush()
    booking(db, org, room, title="Robotics workshop")
    booking(
        db,
        org,
        room,
        title="Approved one",
        status=BookingStatus.APPROVED,
        start_time=time(15, 0),
        end_time=time(16, 30),
    )

    rows = admin.get("/api/admin/bookings/pending").json()

    assert [r["title"] for r in rows] == ["Robotics workshop"]
    assert rows[0]["requester"] == {
        "name": "Clubul de robotica",
        "email": "org@ulbsibiu.ro",
        "role": "STUDENT_ORG",
    }
    assert rows[0]["room_name"] == room.name
    assert rows[0]["specific_date"] == DAY


def test_an_admin_accepts_a_request_and_the_requester_sees_it(db, room, monkeypatch) -> None:
    student = make_client(db)
    user = sign_in(db, student, monkeypatch, "sub-a3", "accept.student@ulbsibiu.ro")
    row = booking(db, user, room)
    admin = make_client(db)
    admin_user = sign_in(
        db, admin, monkeypatch, "sub-a4", "accept.admin@ulbsibiu.ro", role=Role.ADMIN
    )

    r = admin.post(f"/api/admin/bookings/{row.id}/decision", json={"decision": "approve"})

    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    db.refresh(row)
    assert row.status == BookingStatus.APPROVED
    assert row.decided_by_id == admin_user.id
    assert row.decided_at is not None
    assert row.decision_message is None
    mine = student.get("/api/bookings/my").json()[0]
    assert mine["status"] == "approved" and mine["decision_message"] is None


def test_an_admin_rejects_with_a_message_and_the_requester_reads_it(db, room, monkeypatch) -> None:
    student = make_client(db)
    user = sign_in(db, student, monkeypatch, "sub-a5", "reject.student@ulbsibiu.ro")
    row = booking(db, user, room)
    admin = make_client(db)
    sign_in(db, admin, monkeypatch, "sub-a6", "reject.admin@ulbsibiu.ro", role=Role.ADMIN)

    r = admin.post(
        f"/api/admin/bookings/{row.id}/decision",
        json={"decision": "reject", "message": "Sala e rezervată pentru un examen."},
    )

    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    mine = student.get("/api/bookings/my").json()[0]
    assert mine["status"] == "rejected"
    assert mine["decision_message"] == "Sala e rezervată pentru un examen."


def test_a_rejection_without_a_message_stores_none(db, room, monkeypatch) -> None:
    student = make_client(db)
    user = sign_in(db, student, monkeypatch, "sub-a7", "quiet.student@ulbsibiu.ro")
    row = booking(db, user, room)
    admin = make_client(db)
    sign_in(db, admin, monkeypatch, "sub-a8", "quiet.admin@ulbsibiu.ro", role=Role.ADMIN)

    admin.post(
        f"/api/admin/bookings/{row.id}/decision", json={"decision": "reject", "message": "   "}
    )

    db.refresh(row)
    assert row.status == BookingStatus.REJECTED
    assert row.decision_message is None


def test_a_message_longer_than_100_characters_is_refused(db, room, monkeypatch) -> None:
    student = make_client(db)
    user = sign_in(db, student, monkeypatch, "sub-a9", "long.student@ulbsibiu.ro")
    row = booking(db, user, room)
    admin = make_client(db)
    sign_in(db, admin, monkeypatch, "sub-a10", "long.admin@ulbsibiu.ro", role=Role.ADMIN)

    r = admin.post(
        f"/api/admin/bookings/{row.id}/decision", json={"decision": "reject", "message": "x" * 101}
    )

    assert r.status_code == 422
    db.refresh(row)
    assert row.status == BookingStatus.PENDING


def test_only_a_pending_request_can_be_decided(db, room, monkeypatch) -> None:
    student = make_client(db)
    user = sign_in(db, student, monkeypatch, "sub-a11", "decided.student@ulbsibiu.ro")
    row = booking(db, user, room, status=BookingStatus.APPROVED)
    admin = make_client(db)
    sign_in(db, admin, monkeypatch, "sub-a12", "decided.admin@ulbsibiu.ro", role=Role.ADMIN)

    r = admin.post(f"/api/admin/bookings/{row.id}/decision", json={"decision": "reject"})

    assert r.status_code == 409
    db.refresh(row)
    assert row.status == BookingStatus.APPROVED


def test_accepting_a_request_that_now_clashes_is_409(db, room, monkeypatch) -> None:
    student = make_client(db)
    user = sign_in(db, student, monkeypatch, "sub-a13", "clash.student@ulbsibiu.ro")
    pending = booking(db, user, room, start_time=time(13, 0), end_time=time(14, 30))
    booking(
        db, user, room, start_time=time(13, 0), end_time=time(14, 30), status=BookingStatus.APPROVED
    )
    admin = make_client(db)
    sign_in(db, admin, monkeypatch, "sub-a14", "clash.admin@ulbsibiu.ro", role=Role.ADMIN)

    r = admin.post(f"/api/admin/bookings/{pending.id}/decision", json={"decision": "approve"})

    assert r.status_code == 409
    db.refresh(pending)
    assert pending.status == BookingStatus.PENDING


def test_a_student_cannot_decide(db, room, monkeypatch) -> None:
    student = make_client(db)
    user = sign_in(db, student, monkeypatch, "sub-a15", "nodecide.student@ulbsibiu.ro")
    row = booking(db, user, room)

    r = student.post(f"/api/admin/bookings/{row.id}/decision", json={"decision": "approve"})

    assert r.status_code == 403
    db.refresh(row)
    assert row.status == BookingStatus.PENDING


def test_an_unknown_request_is_404_and_a_bad_decision_is_422(db, room, monkeypatch) -> None:
    admin = make_client(db)
    sign_in(db, admin, monkeypatch, "sub-a16", "unknown.admin@ulbsibiu.ro", role=Role.ADMIN)
    assert (
        admin.post(
            f"/api/admin/bookings/{uuid.uuid4()}/decision", json={"decision": "approve"}
        ).status_code
        == 404
    )

    user = db.scalar(select(User).where(User.email == "unknown.admin@ulbsibiu.ro"))
    row = booking(db, user, room)
    assert (
        admin.post(f"/api/admin/bookings/{row.id}/decision", json={"decision": "maybe"}).status_code
        == 422
    )
