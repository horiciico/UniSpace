"""Booking history for admins (GET /api/admin/bookings) and an admin's cancel of a future approved booking.

Filters: faculty_id (a faculty, or "campus" for rooms with no faculty), classroom_id, status. Paging:
limit (default 50, at most 200) and offset. Newest first: date, then start time, then when it was made.
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
from app.models import Booking, BookingStatus, Classroom, Faculty, Role, User
from app.planning import LOCAL_TZ

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=LOCAL_TZ)


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.routers.bookings.local_now", lambda: NOW)
    monkeypatch.setattr("app.routers.admin_bookings.local_now", lambda: NOW)


@pytest.fixture(autouse=True)
def reset_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


def make_client(db: Session) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, base_url="https://testserver")


def sign_in(db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch, sub: str, email: str,
            role: Role = Role.STUDENT) -> User:
    claims = {"sub": sub, "email": email, "email_verified": True, "hd": "ulbsibiu.ro", "name": "Test"}

    async def fake(request):
        return {"userinfo": claims}

    monkeypatch.setattr(oauth.google, "authorize_access_token", fake)
    client.get("/auth/callback", follow_redirects=False)
    user = db.scalar(select(User).where(User.email == email))
    user.role = role
    db.flush()
    return user


def make_user(db: Session, email: str, role: Role = Role.STUDENT) -> User:
    user = User(email=email, name=email.split("@")[0], role=role)
    db.add(user)
    db.flush()
    return user


def make_room(db: Session, faculty: Faculty | None = None) -> Classroom:
    tag = uuid.uuid4().hex[:8]
    room = Classroom(name=f"H-{tag}", capacity=30, faculty_id=faculty.id if faculty else None,
                     external_id=f"h-{tag}")
    db.add(room)
    db.flush()
    return room


def make_booking(db: Session, user: User, room: Classroom, **kw) -> Booking:
    values = dict(user_id=user.id, classroom_id=room.id, specific_date=date(2026, 12, 14),
                  start_time=time(13, 0), end_time=time(14, 30), title="Club")
    values.update(kw)
    row = Booking(**values)
    db.add(row)
    db.flush()
    return row


def admin_client(db: Session, monkeypatch: pytest.MonkeyPatch, email: str) -> TestClient:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-" + email, email, role=Role.ADMIN)
    return client


@pytest.fixture
def faculty(db: Session) -> Faculty:
    tag = uuid.uuid4().hex[:8]
    faculty = Faculty(code=f"h{tag}", name="Facultatea de Istorie")
    db.add(faculty)
    db.flush()
    return faculty


def test_history_is_for_admins_only(db, monkeypatch) -> None:
    student = make_client(db)
    sign_in(db, student, monkeypatch, "sub-hs", "history.student@ulbsibiu.ro")
    assert student.get("/api/admin/bookings").status_code == 403
    assert make_client(db).get("/api/admin/bookings").status_code == 401


def test_history_lists_every_status_newest_first(db, monkeypatch) -> None:
    admin = admin_client(db, monkeypatch, "history.admin1@ulbsibiu.ro")
    room = make_room(db)
    user = make_user(db, "h-order@ulbsibiu.ro")
    early = make_booking(db, user, room, specific_date=date(2026, 12, 1), start_time=time(8, 0),
                         end_time=time(9, 30))
    rejected = make_booking(db, user, room, specific_date=date(2026, 12, 2), start_time=time(8, 0),
                            end_time=time(9, 30), status=BookingStatus.REJECTED)
    later = make_booking(db, user, room, specific_date=date(2026, 12, 2), start_time=time(13, 0),
                         end_time=time(14, 30), status=BookingStatus.CANCELLED)

    data = admin.get("/api/admin/bookings", params={"classroom_id": str(room.id)}).json()

    assert [i["id"] for i in data["items"]] == [str(later.id), str(rejected.id), str(early.id)]
    item = data["items"][0]
    assert item["user_email"] == "h-order@ulbsibiu.ro" and item["user_role"] == "STUDENT"
    assert item["classroom_name"] == room.name and item["status"] == "cancelled"
    assert data["total"] == 3 and data["limit"] == 50 and data["offset"] == 0


def test_history_filters_by_faculty_and_by_campus(db, faculty, monkeypatch) -> None:
    admin = admin_client(db, monkeypatch, "history.admin2@ulbsibiu.ro")
    user = make_user(db, "h-fac@ulbsibiu.ro")
    owned = make_room(db, faculty)
    campus_room = make_room(db)
    in_faculty = make_booking(db, user, owned, title="In faculty")
    on_campus = make_booking(db, user, campus_room, title="On campus")

    by_faculty = admin.get("/api/admin/bookings", params={"faculty_id": str(faculty.id)}).json()["items"]
    campus = admin.get("/api/admin/bookings", params={"faculty_id": "campus"}).json()["items"]

    assert [i["id"] for i in by_faculty] == [str(in_faculty.id)]
    assert by_faculty[0]["faculty_id"] == str(faculty.id)
    assert by_faculty[0]["faculty_name"] == "Facultatea de Istorie"
    assert str(on_campus.id) in {i["id"] for i in campus}
    assert str(in_faculty.id) not in {i["id"] for i in campus}
    assert all(i["faculty_id"] is None and i["faculty_name"] is None for i in campus)


def test_history_filters_by_room_status_and_both(db, monkeypatch) -> None:
    admin = admin_client(db, monkeypatch, "history.admin3@ulbsibiu.ro")
    user = make_user(db, "h-room@ulbsibiu.ro")
    room = make_room(db)
    other = make_room(db)
    approved_here = make_booking(db, user, room, title="A", status=BookingStatus.APPROVED,
                                 specific_date=date(2026, 12, 3))
    rejected_here = make_booking(db, user, room, title="B", status=BookingStatus.REJECTED,
                                 specific_date=date(2026, 12, 3), start_time=time(15, 0), end_time=time(16, 30))
    approved_there = make_booking(db, user, other, title="C", status=BookingStatus.APPROVED,
                                  specific_date=date(2026, 12, 3), start_time=time(17, 0), end_time=time(18, 30))

    by_room = admin.get("/api/admin/bookings", params={"classroom_id": str(room.id)}).json()["items"]
    by_status = admin.get("/api/admin/bookings", params={"status": "approved"}).json()["items"]
    both = admin.get("/api/admin/bookings",
                     params={"classroom_id": str(other.id), "status": "approved"}).json()

    assert {i["id"] for i in by_room} == {str(approved_here.id), str(rejected_here.id)}
    assert {str(approved_here.id), str(approved_there.id)} <= {i["id"] for i in by_status}
    assert str(rejected_here.id) not in {i["id"] for i in by_status}
    assert [i["id"] for i in both["items"]] == [str(approved_there.id)]
    assert both["total"] == 1


def test_history_pages_with_limit_and_offset(db, monkeypatch) -> None:
    admin = admin_client(db, monkeypatch, "history.admin4@ulbsibiu.ro")
    user = make_user(db, "h-page@ulbsibiu.ro")
    room = make_room(db)
    for hour in (8, 9, 10):
        make_booking(db, user, room, title=f"Page {hour}", specific_date=date(2027, 1, 4),
                     start_time=time(hour, 0), end_time=time(hour, 30), status=BookingStatus.CANCELLED)
    params = {"classroom_id": str(room.id), "status": "cancelled", "limit": 2}

    first = admin.get("/api/admin/bookings", params={**params, "offset": 0}).json()
    rest = admin.get("/api/admin/bookings", params={**params, "offset": 2}).json()

    assert first["total"] == 3 and first["limit"] == 2
    assert [i["title"] for i in first["items"]] == ["Page 10", "Page 9"]
    assert rest["offset"] == 2 and [i["title"] for i in rest["items"]] == ["Page 8"]


def test_history_refuses_bad_filters(db, monkeypatch) -> None:
    admin = admin_client(db, monkeypatch, "history.admin5@ulbsibiu.ro")
    assert admin.get("/api/admin/bookings", params={"faculty_id": "not-a-uuid"}).status_code == 400
    assert admin.get("/api/admin/bookings", params={"limit": 0}).status_code == 422
    assert admin.get("/api/admin/bookings", params={"limit": 201}).status_code == 422
    assert admin.get("/api/admin/bookings", params={"status": "maybe"}).status_code == 422


def test_an_admin_cancels_another_users_future_approved_booking(db, monkeypatch) -> None:
    student = make_client(db)
    user = sign_in(db, student, monkeypatch, "sub-hf", "future.student@ulbsibiu.ro")
    room = make_room(db)
    future = make_booking(db, user, room, status=BookingStatus.APPROVED, specific_date=date(2026, 12, 20))
    admin = admin_client(db, monkeypatch, "future.admin@ulbsibiu.ro")

    r = admin.post(f"/api/admin/bookings/{future.id}/cancel")

    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
    db.refresh(future)
    assert future.status == BookingStatus.CANCELLED


def test_admin_cancel_refuses_past_or_pending_and_non_admins(db, monkeypatch) -> None:
    student = make_client(db)
    user = sign_in(db, student, monkeypatch, "sub-hp", "refuse.student@ulbsibiu.ro")
    room = make_room(db)
    past = make_booking(db, user, room, status=BookingStatus.APPROVED, specific_date=date(2026, 11, 1))
    pending = make_booking(db, user, room, status=BookingStatus.PENDING, specific_date=date(2026, 12, 21))
    future = make_booking(db, user, room, status=BookingStatus.APPROVED, specific_date=date(2026, 12, 22))
    admin = admin_client(db, monkeypatch, "refuse.admin@ulbsibiu.ro")

    assert admin.post(f"/api/admin/bookings/{past.id}/cancel").status_code == 409
    assert admin.post(f"/api/admin/bookings/{pending.id}/cancel").status_code == 409
    assert student.post(f"/api/admin/bookings/{future.id}/cancel").status_code == 403
    db.refresh(future)
    assert future.status == BookingStatus.APPROVED
