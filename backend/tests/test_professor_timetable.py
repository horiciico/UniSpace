"""A professor's own timetable and movable activities (GET /api/professors/me/*).

Professor identity: LOWER(users.email) == LOWER(professors.email) (business rule 6). A PROFESSOR
user with no professors row is unlinked: no activities, and a clear `linked: false`.
Week 7 (2026-11-16) is ODD and week 8 (2026-11-23) is EVEN; the unit starts Monday 2026-10-05.
Today is fixed at 2026-11-20 for the "upcoming" rules.
"""

import uuid
from collections.abc import Iterator
from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import oauth
from app.db import get_db
from app.main import app
from app.models import (
    Activity,
    ActivityException,
    ActivityGroup,
    ActivityType,
    Classroom,
    Faculty,
    Parity,
    PlanningTimeUnit,
    PlanningUnitType,
    Priority,
    Professor,
    Role,
    Status,
    StudentGroup,
    User,
)
from app.professors import get_professor_for_user

TODAY = date(2026, 11, 20)
MON_ODD = "2026-11-16"  # week 7
MON_EVEN = "2026-11-23"  # week 8


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.routers.professors.local_today", lambda: TODAY)


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
    role: Role,
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
def world(db: Session) -> dict:
    tag = uuid.uuid4().hex[:8]
    faculty = Faculty(code=f"p{tag}", name="Facultatea de Test")
    db.add(faculty)
    db.flush()
    unit = PlanningTimeUnit(
        faculty_id=faculty.id,
        external_id=1,
        year=2026,
        name="Semestrul 1",
        type=PlanningUnitType.SEMESTER,
        start_date=date(2026, 10, 5),
        end_date=date(2027, 1, 31),
    )
    db.add(unit)
    db.flush()
    room = Classroom(name=f"R-{tag}", capacity=30, faculty_id=faculty.id, external_id=f"r-{tag}")
    db.add(room)
    db.flush()

    ulbs_id = uuid.uuid4()
    email = f"prof.{tag}@ulbsibiu.ro"
    db.add(Professor(id=ulbs_id, name=f"Prof {tag}", email=email))
    db.flush()

    def weekly(name: str, **kw) -> Activity:
        values = dict(
            name=name,
            type=ActivityType.COURSE,
            priority=Priority.COURSE,
            classroom_id=room.id,
            day_of_week=1,
            start_time=time(10, 0),
            end_time=time(12, 0),
            parity=Parity.ALL,
            planning_time_unit_id=unit.id,
            external_id=f"{name}-{tag}",
            professor_id=ulbs_id,
            professor_name=f"Prof {tag}",
        )
        values.update(kw)
        return Activity(**values)

    algebra = weekly("Algebra", parity=Parity.ODD)
    seminar = weekly("Seminar", day_of_week=3, start_time=time(13, 0), end_time=time(14, 0))
    moved = weekly("Moved lecture", day_of_week=5, start_time=time(9, 0), end_time=time(10, 0))
    cancelled_occurrence = weekly(
        "Cancelled occurrence", day_of_week=4, start_time=time(9, 0), end_time=time(10, 0)
    )
    cancelled_course = weekly("Cancelled course", day_of_week=2, status=Status.CANCELLED)
    colocviu = Activity(
        name="Colocviu",
        type=ActivityType.EXAM,
        priority=Priority.EXAM,
        classroom_id=room.id,
        day_of_week=2,
        start_time=time(15, 0),
        end_time=time(16, 0),
        parity=Parity.ALL,
        specific_date=date(2026, 11, 17),
        professor_id=ulbs_id,
        professor_name=f"Prof {tag}",
    )
    far_one_off = Activity(
        name="Sustinere",
        type=ActivityType.EXAM,
        priority=Priority.EXAM,
        classroom_id=room.id,
        day_of_week=2,
        start_time=time(15, 0),
        end_time=time(16, 0),
        parity=Parity.ALL,
        specific_date=date(2026, 12, 1),
        professor_id=ulbs_id,
        professor_name=f"Prof {tag}",
    )
    other_professor = weekly("Other professor", professor_id=uuid.uuid4(), day_of_week=1)
    name_only = weekly("Name only", professor_id=None, day_of_week=1)
    db.add_all(
        [
            algebra,
            seminar,
            moved,
            cancelled_occurrence,
            cancelled_course,
            colocviu,
            far_one_off,
            other_professor,
            name_only,
        ]
    )
    db.flush()
    db.add_all(
        [
            # Friday 2026-11-20 moves to Wednesday 2026-11-18 at 15:00.
            ActivityException(
                activity_id=moved.id,
                original_date=date(2026, 11, 20),
                new_date=date(2026, 11, 18),
                new_start_time=time(15, 0),
                new_end_time=time(16, 0),
            ),
            # Thursday 2026-11-19 is cancelled.
            ActivityException(
                activity_id=cancelled_occurrence.id,
                original_date=date(2026, 11, 19),
                is_cancelled=True,
            ),
        ]
    )
    db.flush()
    return {"email": email, "ulbs_id": ulbs_id, "room": room}


def test_the_week_has_the_professors_own_occurrences_only(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-1", world["email"], Role.PROFESSOR)

    body = client.get("/api/professors/me/timetable", params={"week_start": MON_ODD}).json()

    assert body["linked"] is True
    assert body["professor_id"] == str(world["ulbs_id"])
    assert body["week_start"] == MON_ODD
    assert body["week_end"] == "2026-11-22"
    shown = sorted((item["title"], item["date"]) for item in body["activities"])
    assert shown == [
        ("Algebra", "2026-11-16"),
        ("Colocviu", "2026-11-17"),
        ("Moved lecture", "2026-11-18"),
        ("Seminar", "2026-11-18"),
    ]


def test_a_course_on_odd_weeks_is_absent_in_an_even_week(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-1", world["email"], Role.PROFESSOR)

    body = client.get("/api/professors/me/timetable", params={"week_start": MON_EVEN}).json()

    titles = {item["title"] for item in body["activities"]}
    assert "Algebra" not in titles
    assert ("Seminar", "2026-11-25") in {(i["title"], i["date"]) for i in body["activities"]}


def test_a_moved_occurrence_shows_on_its_new_date_and_time_only(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-1", world["email"], Role.PROFESSOR)

    body = client.get("/api/professors/me/timetable", params={"week_start": MON_ODD}).json()

    moved = [item for item in body["activities"] if item["title"] == "Moved lecture"]
    assert len(moved) == 1
    assert moved[0]["date"] == "2026-11-18"
    assert moved[0]["day_of_week"] == 3
    assert moved[0]["start_time"] == "15:00"
    assert moved[0]["end_time"] == "16:00"
    assert moved[0]["is_recurring"] is True


def test_the_item_has_the_timetable_fields(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-1", world["email"], Role.PROFESSOR)

    body = client.get("/api/professors/me/timetable", params={"week_start": MON_ODD}).json()

    seminar = next(item for item in body["activities"] if item["title"] == "Seminar")
    assert set(seminar) == {
        "id",
        "title",
        "activity_type",
        "priority",
        "day_of_week",
        "date",
        "start_time",
        "end_time",
        "parity",
        "room_id",
        "room_name",
        "professor",
        "groups",
        "is_recurring",
    }
    assert seminar["room_id"] == str(world["room"].id)
    assert seminar["room_name"] == world["room"].name
    assert seminar["start_time"] == "13:00"


def test_a_date_inside_the_week_is_snapped_to_its_monday(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-1", world["email"], Role.PROFESSOR)

    body = client.get("/api/professors/me/timetable", params={"week_start": "2026-11-19"}).json()

    assert body["week_start"] == MON_ODD


def test_a_bad_week_start_is_422(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-1", world["email"], Role.PROFESSOR)

    response = client.get("/api/professors/me/timetable", params={"week_start": "soon"})

    assert response.status_code == 422


def test_a_professor_with_no_row_is_unlinked_and_sees_no_activities(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-2", "nobody.linked@ulbsibiu.ro", Role.PROFESSOR)

    body = client.get("/api/professors/me/timetable", params={"week_start": MON_ODD}).json()

    assert body["linked"] is False
    assert body["professor_id"] is None
    assert body["activities"] == []


def test_the_movable_list_is_unlinked_when_there_is_no_row(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-2", "nobody.linked@ulbsibiu.ro", Role.PROFESSOR)

    body = client.get("/api/professors/me/movable-activities").json()

    assert body == {"linked": False, "activities": []}


def test_only_professors_have_a_timetable(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-3", world["email"], Role.STUDENT)

    assert client.get("/api/professors/me/timetable").status_code == 403
    assert client.get("/api/professors/me/movable-activities").status_code == 403


def test_the_timetable_needs_a_sign_in(db, world) -> None:
    client = make_client(db)

    assert client.get("/api/professors/me/timetable").status_code == 401
    assert client.get("/api/professors/me/movable-activities").status_code == 401


def test_movable_activities_are_the_weekly_ones_and_upcoming_one_offs(
    db, world, monkeypatch
) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-1", world["email"], Role.PROFESSOR)

    body = client.get("/api/professors/me/movable-activities").json()

    assert body["linked"] is True
    titles = sorted(item["title"] for item in body["activities"])
    # Colocviu (2026-11-17) is in the past on 2026-11-20; cancelled and other people's are out.
    assert titles == [
        "Algebra",
        "Cancelled occurrence",
        "Moved lecture",
        "Seminar",
        "Sustinere",
    ]


def test_movable_items_carry_their_groups_for_the_availability_check(
    db, world, monkeypatch
) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-1", world["email"], Role.PROFESSOR)
    group = StudentGroup(name=f"G-{uuid.uuid4().hex[:6]}", external_id=uuid.uuid4().int % 10**9)
    db.add(group)
    db.flush()
    seminar = db.scalar(select(Activity).where(Activity.name == "Seminar"))
    db.add(ActivityGroup(activity_id=seminar.id, group_id=group.id))
    db.flush()

    body = client.get("/api/professors/me/movable-activities").json()

    item = next(a for a in body["activities"] if a["title"] == "Seminar")
    assert item["group_ids"] == [str(group.id)]
    assert item["groups"] == [group.name]
    other = next(a for a in body["activities"] if a["title"] == "Algebra")
    assert other["group_ids"] == [] and other["groups"] == []


def test_movable_items_say_whether_they_repeat(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-1", world["email"], Role.PROFESSOR)

    body = client.get("/api/professors/me/movable-activities").json()

    by_title = {item["title"]: item for item in body["activities"]}
    assert by_title["Seminar"]["is_recurring"] is True
    assert by_title["Seminar"]["specific_date"] is None
    assert by_title["Sustinere"]["is_recurring"] is False
    assert by_title["Sustinere"]["specific_date"] == "2026-12-01"
    assert set(by_title["Seminar"]) == {
        "id",
        "title",
        "activity_type",
        "day_of_week",
        "start_time",
        "end_time",
        "room_name",
        "is_recurring",
        "specific_date",
        "group_ids",
        "groups",
    }


def test_the_professor_is_found_by_email_whatever_the_case(db, world) -> None:
    user = User(email=world["email"].upper(), name="Upper", role=Role.PROFESSOR)

    found = get_professor_for_user(db, user)

    assert found is not None
    assert found.id == world["ulbs_id"]


def test_an_address_with_no_professor_row_finds_nothing(db) -> None:
    user = User(email=f"none.{uuid.uuid4().hex}@ulbsibiu.ro", name="None", role=Role.PROFESSOR)

    assert get_professor_for_user(db, user) is None
