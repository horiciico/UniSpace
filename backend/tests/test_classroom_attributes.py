"""Room attributes for the admin Rooms tab and for Free Now.

GET /api/admin/classrooms and PATCH /api/admin/classrooms/{id} are ADMIN only. Free Now
(GET /api/classrooms/free) returns the attributes of each room. DB tests run against the
rolled-back `db` fixture (PATTERN-005, PATTERN-006).
"""
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import oauth
from app.db import get_db
from app.main import app
from app.models import BoardType, Classroom, Faculty, Role, User

DAY = "2026-12-14"


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


@pytest.fixture
def rooms(db: Session) -> dict:
    """A faculty with one room that has a projector and notes, and one campus room."""
    tag = uuid.uuid4().hex[:8]
    faculty = Faculty(code=f"t{tag}", name="Facultatea de Test")
    db.add(faculty)
    db.flush()
    owned = Classroom(name=f"A-{tag}", capacity=30, faculty_id=faculty.id, external_id=f"own-{tag}",
                      has_projector=True, board_type=BoardType.SMARTBOARD, access_notes="Cheia la portar",
                      equipment_notes="24 PC-uri")
    campus = Classroom(name=f"B-{tag}", capacity=10, faculty_id=None, external_id=f"cam-{tag}")
    db.add_all([owned, campus])
    db.flush()
    return {"faculty": faculty, "owned": owned, "campus": campus}


def test_only_an_admin_can_list_or_edit_the_rooms(db: Session, rooms: dict, monkeypatch) -> None:
    student = make_client(db)
    sign_in(db, student, monkeypatch, "sub-r1", "rooms.student@ulbsibiu.ro")
    room_url = f"/api/admin/classrooms/{rooms['owned'].id}"
    assert student.get("/api/admin/classrooms").status_code == 403
    assert student.patch(room_url, json={"is_bookable": False}).status_code == 403
    assert make_client(db).get("/api/admin/classrooms").status_code == 401
    assert make_client(db).patch(room_url, json={"is_bookable": False}).status_code == 401


def test_the_admin_list_shows_every_attribute_and_filters_by_faculty(db: Session, rooms: dict, monkeypatch) -> None:
    admin = make_client(db)
    sign_in(db, admin, monkeypatch, "sub-r2", "rooms.admin@ulbsibiu.ro", role=Role.ADMIN)

    everything = {row["id"]: row for row in admin.get("/api/admin/classrooms").json()}
    assert everything[str(rooms["owned"].id)] == {
        "id": str(rooms["owned"].id), "name": rooms["owned"].name, "faculty_id": str(rooms["faculty"].id),
        "capacity": 30, "is_bookable": True, "has_projector": True, "board_type": "smartboard",
        "access_notes": "Cheia la portar", "equipment_notes": "24 PC-uri",
    }
    own_only = admin.get("/api/admin/classrooms", params={"faculty_id": str(rooms["faculty"].id)}).json()
    assert [row["id"] for row in own_only] == [str(rooms["owned"].id)]
    campus = admin.get("/api/admin/classrooms", params={"faculty_id": "campus"}).json()
    assert str(rooms["campus"].id) in {row["id"] for row in campus}
    assert str(rooms["owned"].id) not in {row["id"] for row in campus}
    assert admin.get("/api/admin/classrooms", params={"faculty_id": "not-a-uuid"}).status_code == 400


def test_a_patch_changes_only_the_fields_sent(db: Session, rooms: dict, monkeypatch) -> None:
    admin = make_client(db)
    sign_in(db, admin, monkeypatch, "sub-r3", "patch.admin@ulbsibiu.ro", role=Role.ADMIN)
    url = f"/api/admin/classrooms/{rooms['owned'].id}"

    r = admin.patch(url, json={"is_bookable": False})
    assert r.status_code == 200
    assert r.json()["is_bookable"] is False
    assert r.json()["has_projector"] is True
    assert r.json()["access_notes"] == "Cheia la portar"

    r = admin.patch(url, json={
        "has_projector": None, "board_type": "whiteboard", "access_notes": "  Portarul, etajul 2  ",
        "equipment_notes": "",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["has_projector"] is None
    assert body["board_type"] == "whiteboard"
    assert body["access_notes"] == "Portarul, etajul 2"
    assert body["equipment_notes"] is None
    assert body["is_bookable"] is False


def test_a_patch_rejects_bad_values_and_unknown_rooms(db: Session, rooms: dict, monkeypatch) -> None:
    admin = make_client(db)
    sign_in(db, admin, monkeypatch, "sub-r4", "bad.admin@ulbsibiu.ro", role=Role.ADMIN)
    url = f"/api/admin/classrooms/{rooms['owned'].id}"

    assert admin.patch(url, json={"board_type": "chalk"}).status_code == 422
    assert admin.patch(url, json={"access_notes": "x" * 256}).status_code == 422
    assert admin.patch(url, json={"equipment_notes": "x" * 501}).status_code == 422
    assert admin.patch(url, json={"is_bookable": None}).status_code == 422
    assert admin.patch(f"/api/admin/classrooms/{uuid.uuid4()}", json={"is_bookable": False}).status_code == 404


def test_free_now_returns_the_attributes_and_filters_by_capacity_and_projector(db: Session, rooms: dict) -> None:
    client = make_client(db)
    params = {"date": DAY, "start_time": "09:40", "end_time": "11:10", "faculty_id": str(rooms["faculty"].id)}
    # A second room of the faculty whose projector is unknown (NULL), with no notes.
    unknown = Classroom(name=f"U-{uuid.uuid4().hex[:6]}", capacity=50, faculty_id=rooms["faculty"].id,
                        external_id=f"unk-{uuid.uuid4().hex[:8]}")
    db.add(unknown)
    db.flush()

    rows = {row["id"]: row for row in client.get("/api/classrooms/free", params=params).json()}
    assert rows[str(rooms["owned"].id)]["board_type"] == "smartboard"
    assert rows[str(rooms["owned"].id)]["access_notes"] == "Cheia la portar"
    assert rows[str(rooms["owned"].id)]["equipment_notes"] == "24 PC-uri"
    assert rows[str(unknown.id)]["has_projector"] is None

    big = client.get("/api/classrooms/free", params={**params, "min_capacity": 40}).json()
    assert [row["id"] for row in big] == [str(unknown.id)]
    projector = client.get("/api/classrooms/free", params={**params, "has_projector": "true"}).json()
    assert [row["id"] for row in projector] == [str(rooms["owned"].id)]
