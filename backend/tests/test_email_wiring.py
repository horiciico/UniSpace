"""Email (step 2): the endpoints queue the right email, after the change is saved.

- POST /api/admin/invitations sends the invitation with the full link
  (APP_BASE_URL + /login?invite=).
- POST /api/admin/bookings/{id}/decision sends the approval or the rejection to the requester. A
  rejection carries the admin's reason when there is one. A refused decision sends nothing.
- A booking an admin makes is approved at once and sends nothing; a student's request sends nothing
  until an admin decides.
- A failing SMTP server never fails the request.

The messages are recorded by replacing `send`; the SMTP class is faked where the real path
is tested.
DB tests: the endpoints run against the rolled-back `db` fixture (PATTERN-005, PATTERN-006).
"""

import uuid
from collections.abc import Iterator
from datetime import date, datetime, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.auth import oauth
from app.db import get_db
from app.email_service import EmailMessage
from app.main import app
from app.models import Booking, BookingStatus, Classroom, Role, User
from app.planning import LOCAL_TZ

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=LOCAL_TZ)


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.routers.bookings.local_now", lambda: NOW)


@pytest.fixture(autouse=True)
def reset_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[EmailMessage]:
    """Every message the endpoints send, in order."""
    messages: list[EmailMessage] = []
    monkeypatch.setattr("app.email_service.send", messages.append)
    return messages


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
    row = Classroom(name=f"Aula-{tag}", capacity=30, external_id=f"r-{tag}")
    db.add(row)
    db.flush()
    return row


def pending(db: Session, user: User, room: Classroom, **kw) -> Booking:
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


@pytest.fixture
def admin(db: Session, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "mail-root", "mail.root@ulbsibiu.ro", Role.ADMIN)
    return client


# ---- Invitations -------------------------------------------------------------


def test_the_invitation_is_sent_with_the_full_link_and_role(
    db: Session, admin: TestClient, sent: list[EmailMessage]
) -> None:
    r = admin.post("/api/admin/invitations", json={"email": "Reps@Club.ro", "role": "STUDENT_ORG"})

    assert r.status_code == 201
    assert len(sent) == 1
    message = sent[0]
    link = f"{config.APP_BASE_URL}/login?invite={r.json()['token']}"
    assert message.to == "reps@club.ro"
    assert message.hidden == link
    assert link in message.body
    assert f'href="{link}"' in message.html
    assert "Student organization" in message.body
    assert "Organizație studențească" in message.body


def test_a_refused_invitation_sends_nothing(
    db: Session, admin: TestClient, sent: list[EmailMessage]
) -> None:
    db.add(User(email="taken@ulbsibiu.ro", name="Taken", role=Role.STUDENT))
    db.flush()

    r = admin.post(
        "/api/admin/invitations", json={"email": "taken@ulbsibiu.ro", "role": "PROFESSOR"}
    )

    assert r.status_code == 409
    assert sent == []


def test_a_failed_smtp_send_does_not_fail_the_invitation(
    db: Session, admin: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class DownServer:
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise OSError("connection refused")

    monkeypatch.setattr(config, "EMAIL_BACKEND", "smtp")
    monkeypatch.setattr("app.email_service.smtplib.SMTP", DownServer)

    r = admin.post("/api/admin/invitations", json={"email": "later@club.ro", "role": "STUDENT"})

    assert r.status_code == 201


# ---- Booking decisions -------------------------------------------------------


def test_an_approval_is_sent_to_the_requester_with_the_booking(
    db: Session,
    admin: TestClient,
    room: Classroom,
    monkeypatch: pytest.MonkeyPatch,
    sent: list[EmailMessage],
) -> None:
    student = make_client(db)
    user = sign_in(db, student, monkeypatch, "mail-s1", "req.approve@ulbsibiu.ro")
    row = pending(db, user, room, title="Seminar robotica")

    r = admin.post(f"/api/admin/bookings/{row.id}/decision", json={"decision": "approve"})

    assert r.status_code == 200
    assert len(sent) == 1
    message = sent[0]
    assert message.to == "req.approve@ulbsibiu.ro"
    assert "aprobată" in message.subject and "approved" in message.subject
    for part in (room.name, "14.12.2026", "13:00–14:30", "Seminar robotica"):
        assert part in message.body
    assert "Motiv" not in message.body and "Reason" not in message.body


def test_a_rejection_sends_the_admins_reason_in_both_languages(
    db: Session,
    admin: TestClient,
    room: Classroom,
    monkeypatch: pytest.MonkeyPatch,
    sent: list[EmailMessage],
) -> None:
    student = make_client(db)
    user = sign_in(db, student, monkeypatch, "mail-s2", "req.reject@ulbsibiu.ro")
    row = pending(db, user, room)

    r = admin.post(
        f"/api/admin/bookings/{row.id}/decision",
        json={"decision": "reject", "message": "Sala e ocupată"},
    )

    assert r.status_code == 200
    assert len(sent) == 1
    assert sent[0].to == "req.reject@ulbsibiu.ro"
    assert "respinsă" in sent[0].subject and "rejected" in sent[0].subject
    assert "Motiv: Sala e ocupată" in sent[0].body
    assert "Reason: Sala e ocupată" in sent[0].body


def test_a_rejection_without_a_message_has_no_reason_line(
    db: Session,
    admin: TestClient,
    room: Classroom,
    monkeypatch: pytest.MonkeyPatch,
    sent: list[EmailMessage],
) -> None:
    student = make_client(db)
    user = sign_in(db, student, monkeypatch, "mail-s3", "req.silent@ulbsibiu.ro")
    row = pending(db, user, room)

    admin.post(f"/api/admin/bookings/{row.id}/decision", json={"decision": "reject"})

    assert len(sent) == 1
    assert "Motiv" not in sent[0].body and "Reason" not in sent[0].body


def test_an_approval_that_now_clashes_sends_nothing(
    db: Session,
    admin: TestClient,
    room: Classroom,
    monkeypatch: pytest.MonkeyPatch,
    sent: list[EmailMessage],
) -> None:
    student = make_client(db)
    user = sign_in(db, student, monkeypatch, "mail-s4", "req.clash@ulbsibiu.ro")
    pending(db, user, room, status=BookingStatus.APPROVED)
    row = pending(db, user, room, title="Later request")

    r = admin.post(f"/api/admin/bookings/{row.id}/decision", json={"decision": "approve"})

    assert r.status_code == 409
    assert sent == []


def test_a_decision_on_a_decided_request_sends_nothing(
    db: Session,
    admin: TestClient,
    room: Classroom,
    monkeypatch: pytest.MonkeyPatch,
    sent: list[EmailMessage],
) -> None:
    student = make_client(db)
    user = sign_in(db, student, monkeypatch, "mail-s5", "req.done@ulbsibiu.ro")
    row = pending(db, user, room, status=BookingStatus.REJECTED)

    r = admin.post(f"/api/admin/bookings/{row.id}/decision", json={"decision": "approve"})

    assert r.status_code == 409
    assert sent == []


def test_a_failed_smtp_send_does_not_fail_the_decision(
    db: Session, admin: TestClient, room: Classroom, monkeypatch: pytest.MonkeyPatch
) -> None:
    class DownServer:
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise OSError("connection refused")

    student = make_client(db)
    user = sign_in(db, student, monkeypatch, "mail-s6", "req.down@ulbsibiu.ro")
    row = pending(db, user, room)
    monkeypatch.setattr(config, "EMAIL_BACKEND", "smtp")
    monkeypatch.setattr("app.email_service.smtplib.SMTP", DownServer)

    r = admin.post(f"/api/admin/bookings/{row.id}/decision", json={"decision": "approve"})

    assert r.status_code == 200
    db.refresh(row)
    assert row.status == BookingStatus.APPROVED


# ---- Who gets no email -------------------------------------------------------


def test_an_admins_own_booking_is_approved_and_sends_nothing(
    db: Session, admin: TestClient, room: Classroom, sent: list[EmailMessage]
) -> None:
    r = admin.post(
        "/api/bookings",
        json={
            "classroom_id": str(room.id),
            "specific_date": "2026-12-14",
            "start_time": "08:00:00",
            "end_time": "09:30:00",
            "title": "Admin's own event",
        },
    )

    assert r.status_code == 201
    assert r.json()["status"] == "approved"
    assert sent == []


def test_a_student_request_sends_nothing_until_it_is_decided(
    db: Session, room: Classroom, monkeypatch: pytest.MonkeyPatch, sent: list[EmailMessage]
) -> None:
    student = make_client(db)
    sign_in(db, student, monkeypatch, "mail-s7", "req.new@ulbsibiu.ro")

    r = student.post(
        "/api/bookings",
        json={
            "classroom_id": str(room.id),
            "specific_date": "2026-12-14",
            "start_time": "08:00:00",
            "end_time": "09:30:00",
            "title": "Club meeting",
        },
    )

    assert r.status_code == 201
    assert r.json()["status"] == "pending"
    assert sent == []
