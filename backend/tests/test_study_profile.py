"""Student onboarding (D-022): the faculty and study formation chosen on first sign-in.

Google is mocked at the authlib client; the database is real and rolled back (PATTERN-005, PATTERN-006).
"""
import os
import uuid
from collections.abc import Iterator
from datetime import date, time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import oauth
from app.db import get_db
from app.main import app
from app.models import (
    Activity,
    ActivityGroup,
    ActivityType,
    Classroom,
    Faculty,
    PlanningTimeUnit,
    PlanningUnitType,
    Priority,
    Professor,
    Role,
    StudentGroup,
    User,
)


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.clear()


def google_returns(monkeypatch: pytest.MonkeyPatch, sub: str, email: str) -> None:
    claims = {"sub": sub, "email": email, "email_verified": True, "hd": "ulbsibiu.ro", "name": "Test"}

    async def fake(request):
        return {"userinfo": claims}

    monkeypatch.setattr(oauth.google, "authorize_access_token", fake)


def sign_in(client: TestClient, monkeypatch: pytest.MonkeyPatch, sub: str, email: str) -> None:
    google_returns(monkeypatch, sub, email)
    client.get("/auth/callback", follow_redirects=False)


@pytest.fixture
def world(db: Session) -> dict:
    """Two faculties. The first has one formation (a group with an activity in its planning unit)."""
    tag = uuid.uuid4().hex[:8]
    first = Faculty(code=f"a{tag}", name="Facultatea A")
    second = Faculty(code=f"b{tag}", name="Facultatea B")
    db.add_all([first, second])
    db.flush()
    unit = PlanningTimeUnit(
        faculty_id=first.id, external_id=1, year=2026, name="Semestrul 1",
        type=PlanningUnitType.SEMESTER, start_date=date(2026, 10, 5), end_date=date(2027, 1, 31),
    )
    db.add(unit)
    db.flush()
    formation = StudentGroup(name=f"F-{tag}", external_id=int(tag, 16) % 2_000_000_000)
    db.add(formation)
    db.flush()
    room = Classroom(name=f"R-{tag}", capacity=30, faculty_id=first.id, external_id=f"r-{tag}")
    db.add(room)
    db.flush()
    course = Activity(
        name="Algebra", type=ActivityType.COURSE, priority=Priority.COURSE, classroom_id=room.id,
        day_of_week=1, start_time=time(10, 0), end_time=time(12, 0), planning_time_unit_id=unit.id,
        external_id=f"c-{tag}",
    )
    db.add(course)
    db.flush()
    db.add(ActivityGroup(activity_id=course.id, group_id=formation.id))
    db.flush()
    return {"first": first, "second": second, "formation": formation, "tag": tag}


def test_a_new_student_needs_onboarding(client, db, monkeypatch) -> None:
    sign_in(client, monkeypatch, "sub-new", "new.student@ulbsibiu.ro")

    me = client.get("/auth/me").json()

    assert me["role"] == "STUDENT"
    assert me["needs_onboarding"] is True
    assert me["faculty_id"] is None
    assert me["study_formation_id"] is None


def test_saving_the_choice_stores_it_and_ends_onboarding(client, db, world, monkeypatch) -> None:
    sign_in(client, monkeypatch, "sub-save", "save.student@ulbsibiu.ro")

    r = client.put("/api/me/study-profile", json={
        "faculty_id": str(world["first"].id), "study_formation_id": str(world["formation"].id),
    })

    assert r.status_code == 200
    assert r.json()["needs_onboarding"] is False
    user = db.scalar(select(User).where(User.email == "save.student@ulbsibiu.ro"))
    assert user.faculty_id == world["first"].id
    assert user.study_formation_id == world["formation"].id


def test_saving_needs_a_session(client, world) -> None:
    r = client.put("/api/me/study-profile", json={
        "faculty_id": str(world["first"].id), "study_formation_id": str(world["formation"].id),
    })
    assert r.status_code == 401


def test_only_students_can_save_a_profile(client, db, world, monkeypatch) -> None:
    db.add(Professor(id=uuid.uuid4(), name="Prof", email="prof@ulbsibiu.ro"))  # the list gives the role (D-020)
    db.commit()
    sign_in(client, monkeypatch, "sub-prof", "prof@ulbsibiu.ro")

    r = client.put("/api/me/study-profile", json={
        "faculty_id": str(world["first"].id), "study_formation_id": str(world["formation"].id),
    })

    assert r.status_code == 403
    user = db.scalar(select(User).where(User.email == "prof@ulbsibiu.ro"))
    assert user.faculty_id is None
    assert user.study_formation_id is None


def test_formation_must_belong_to_the_chosen_faculty(client, world, monkeypatch) -> None:
    sign_in(client, monkeypatch, "sub-other", "other.student@ulbsibiu.ro")

    r = client.put("/api/me/study-profile", json={
        "faculty_id": str(world["second"].id), "study_formation_id": str(world["formation"].id),
    })

    assert r.status_code == 422


def test_unknown_formation_is_422(client, world, monkeypatch) -> None:
    sign_in(client, monkeypatch, "sub-unknown", "unknown.student@ulbsibiu.ro")

    r = client.put("/api/me/study-profile", json={
        "faculty_id": str(world["first"].id), "study_formation_id": str(uuid.uuid4()),
    })

    assert r.status_code == 422


def test_a_later_sign_in_keeps_the_saved_choice(client, world, monkeypatch) -> None:
    sign_in(client, monkeypatch, "sub-again", "again.student@ulbsibiu.ro")
    client.put("/api/me/study-profile", json={
        "faculty_id": str(world["first"].id), "study_formation_id": str(world["formation"].id),
    })

    sign_in(client, monkeypatch, "sub-again", "again.student@ulbsibiu.ro")
    me = client.get("/auth/me").json()

    assert me["faculty_id"] == str(world["first"].id)
    assert me["study_formation_id"] == str(world["formation"].id)
    assert me["needs_onboarding"] is False


def test_deleting_a_formation_clears_the_choice(db, world) -> None:
    user = User(email=f"gone-{world['tag']}@ulbsibiu.ro", name="Gone", role=Role.STUDENT,
                faculty_id=world["first"].id, study_formation_id=world["formation"].id)
    db.add(user)
    db.flush()

    # A SQL-level delete, so the database's ON DELETE SET NULL is what clears the column.
    db.execute(delete(StudentGroup).where(StudentGroup.id == world["formation"].id))
    db.refresh(user)

    assert user.study_formation_id is None
    assert user.faculty_id == world["first"].id


def test_needs_onboarding_only_for_a_student_without_a_faculty() -> None:
    assert User(role=Role.STUDENT, faculty_id=None).needs_onboarding is True
    assert User(role=Role.STUDENT, faculty_id=uuid.uuid4()).needs_onboarding is False
    assert User(role=Role.PROFESSOR, faculty_id=None).needs_onboarding is False
    assert User(role=Role.ADMIN, faculty_id=None).needs_onboarding is False


def test_the_shared_head_loads_the_onboarding_dependencies_in_order() -> None:
    """The dialog needs api.js (window.UniSpaceApi) and auth.js before it runs, on every page."""
    head = (Path(os.environ.get("FRONTEND_DIR", "/frontend")) / "components" / "head.html").read_text(encoding="utf-8")
    auth, api, onboarding = (head.index(name) for name in ("/js/auth.js", "/js/api.js", "/components/onboarding.js"))
    assert auth < api < onboarding
