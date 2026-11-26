"""Moving one teaching occurrence (POST /api/professors/me/activities/{id}/move, step 3).

Rules (approved 2026-11-26): a weekly occurrence is moved by an ActivityException with
is_cancelled = True plus a new one-off row; a one-off is moved by a new one-off row and the
old one is set CANCELLED. Whole 90-minute modules only; the room must be bookable; a new date
before today is refused; the new slot must be free for the room, the professor and every group
of the activity.

Today is fixed at 2026-11-20. Monday 2026-11-23 is in week 8 (EVEN), and the unit starts 2026-10-05.
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

TODAY = date(2026, 11, 20)
MON = "2026-11-23"  # the weekly Algebra class
TUE = "2026-11-24"
WED = "2026-11-25"
M0 = (time(8, 0), time(9, 30))
M1 = (time(9, 40), time(11, 10))
M2 = (time(13, 0), time(14, 30))


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
    faculty = Faculty(code=f"m{tag}", name="Facultatea de Test")
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

    def room(label: str, **kw) -> Classroom:
        values = dict(
            name=f"{label}-{tag}",
            capacity=30,
            faculty_id=faculty.id,
            external_id=f"{label}-{tag}",
            is_bookable=True,
        )
        values.update(kw)
        return Classroom(**values)

    room_a = room("A")
    room_b = room("B")
    room_off = room("OFF", is_bookable=False)
    db.add_all([room_a, room_b, room_off])
    db.flush()

    group_a = StudentGroup(name=f"GA-{tag}", external_id=int(tag, 16) % 2_000_000_000)
    group_b = StudentGroup(name=f"GB-{tag}", external_id=(int(tag, 16) + 1) % 2_000_000_000)
    db.add_all([group_a, group_b])
    db.flush()

    ulbs_id = uuid.uuid4()
    email = f"prof.{tag}@ulbsibiu.ro"
    db.add(Professor(id=ulbs_id, name=f"Prof {tag}", email=email))
    db.flush()

    def link_groups(activity: Activity, groups: tuple[StudentGroup, ...]) -> None:
        for group in groups:
            db.add(ActivityGroup(activity_id=activity.id, group_id=group.id))
        db.flush()

    def weekly(
        name: str,
        span: tuple[time, time],
        *,
        day: int = 1,
        professor: uuid.UUID | None = None,
        room: Classroom | None = None,
        groups: tuple[StudentGroup, ...] = (),
        status: Status = Status.APPROVED,
    ) -> Activity:
        activity = Activity(
            name=name,
            type=ActivityType.COURSE,
            priority=Priority.COURSE,
            classroom_id=(room or room_a).id,
            day_of_week=day,
            start_time=span[0],
            end_time=span[1],
            parity=Parity.ALL,
            planning_time_unit_id=unit.id,
            external_id=f"{name}-{uuid.uuid4().hex[:6]}",
            professor_id=professor or ulbs_id,
            professor_name=f"Prof {tag}",
            status=status,
        )
        db.add(activity)
        db.flush()
        link_groups(activity, groups)
        return activity

    def one_off(
        name: str,
        on: date,
        span: tuple[time, time],
        *,
        professor: uuid.UUID | None = None,
        room: Classroom | None = None,
        groups: tuple[StudentGroup, ...] = (),
        imported: bool = False,
    ) -> Activity:
        activity = Activity(
            name=name,
            type=ActivityType.EXAM,
            priority=Priority.EXAM,
            classroom_id=(room or room_a).id,
            day_of_week=on.isoweekday(),
            start_time=span[0],
            end_time=span[1],
            parity=Parity.ALL,
            specific_date=on,
            professor_id=professor or ulbs_id,
            professor_name=f"Prof {tag}",
            planning_time_unit_id=unit.id if imported else None,
            external_id=f"{name}-{tag}" if imported else None,
        )
        db.add(activity)
        db.flush()
        link_groups(activity, groups)
        return activity

    algebra = weekly("Algebra", M0, groups=(group_a,))
    return {
        "email": email,
        "ulbs_id": ulbs_id,
        "other": uuid.uuid4(),
        "room_a": room_a,
        "room_b": room_b,
        "room_off": room_off,
        "group_a": group_a,
        "group_b": group_b,
        "algebra": algebra,
        "weekly": weekly,
        "one_off": one_off,
        "link_groups": link_groups,
        "db": db,
    }


def move_body(room: Classroom, **overrides) -> dict:
    body = {
        "original_date": MON,
        "new_date": TUE,
        "start_time": "09:40",
        "end_time": "11:10",
        "new_classroom_id": str(room.id),
    }
    body.update({key: str(value) for key, value in overrides.items()})
    return body


def move(client: TestClient, activity: Activity, body: dict):
    return client.post(f"/api/professors/me/activities/{activity.id}/move", json=body)


def exceptions_of(db: Session, activity: Activity) -> list[ActivityException]:
    return list(
        db.scalars(select(ActivityException).where(ActivityException.activity_id == activity.id))
    )


def timetable_titles(client: TestClient, week_start: str) -> set[tuple[str, str, str]]:
    body = client.get("/api/professors/me/timetable", params={"week_start": week_start}).json()
    return {(a["title"], a["date"], a["start_time"]) for a in body["activities"]}


def free_room_ids(client: TestClient, day: str, start: str, end: str) -> set[str]:
    rooms = client.get(
        "/api/classrooms/free",
        params={"date": day, "start_time": start, "end_time": end},
    ).json()
    return {room["id"] for room in rooms}


@pytest.fixture
def client_signed_in(db, world, monkeypatch) -> TestClient:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-1", world["email"], Role.PROFESSOR)
    return client


# --- a weekly occurrence ----------------------------------------------------------------------


def test_a_weekly_occurrence_moves_to_a_one_off_and_the_original_is_cancelled(
    db, world, client_signed_in
) -> None:
    response = move(client_signed_in, world["algebra"], move_body(world["room_b"]))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["original_date"] == MON
    assert body["date"] == TUE
    assert body["start_time"] == "09:40"
    assert body["end_time"] == "11:10"
    assert body["room_id"] == str(world["room_b"].id)
    assert body["title"] == "Algebra"

    [moved_to] = [
        e for e in exceptions_of(db, world["algebra"]) if e.original_date.isoformat() == MON
    ]
    assert moved_to.is_cancelled is True

    new = db.get(Activity, uuid.UUID(body["id"]))
    assert new.specific_date.isoformat() == TUE
    assert new.day_of_week == 2
    assert new.classroom_id == world["room_b"].id
    assert new.status == Status.APPROVED
    assert new.is_manually_modified is True
    assert new.professor_id == world["ulbs_id"]
    assert new.name == "Algebra"
    assert new.planning_time_unit_id is None


def test_the_new_one_off_keeps_its_group_and_its_mover(db, world, client_signed_in) -> None:
    body = move(client_signed_in, world["algebra"], move_body(world["room_b"])).json()

    new = db.get(Activity, uuid.UUID(body["id"]))
    groups = db.scalars(
        select(ActivityGroup.group_id).where(ActivityGroup.activity_id == new.id)
    ).all()
    assert groups == [world["group_a"].id]
    mover = db.scalar(select(User).where(User.email == world["email"]))
    assert new.user_id == mover.id


def test_the_vacated_slot_is_free_for_the_timetable_and_the_room_search(
    db, world, client_signed_in
) -> None:
    before = free_room_ids(client_signed_in, MON, "08:00", "09:30")
    assert str(world["room_a"].id) not in before

    move(client_signed_in, world["algebra"], move_body(world["room_b"]))

    after = free_room_ids(client_signed_in, MON, "08:00", "09:30")
    assert str(world["room_a"].id) in after
    shown = timetable_titles(client_signed_in, MON)
    assert ("Algebra", MON, "08:00") not in shown
    assert ("Algebra", TUE, "09:40") in shown


def test_the_moved_occurrence_is_listed_as_movable(db, world, client_signed_in) -> None:
    body = move(client_signed_in, world["algebra"], move_body(world["room_b"])).json()

    movable = client_signed_in.get("/api/professors/me/movable-activities").json()["activities"]

    assert any(a["id"] == body["id"] and a["specific_date"] == TUE for a in movable)


def test_a_same_day_move_may_keep_part_of_its_own_slot(db, world, client_signed_in) -> None:
    response = move(
        client_signed_in,
        world["algebra"],
        move_body(world["room_a"], new_date=MON, start_time="08:00", end_time="11:10"),
    )

    assert response.status_code == 200, response.text


def test_a_weekly_occurrence_moves_once(db, world, client_signed_in) -> None:
    assert move(client_signed_in, world["algebra"], move_body(world["room_b"])).status_code == 200

    again = move(client_signed_in, world["algebra"], move_body(world["room_b"], new_date=WED))

    assert again.status_code == 400


def test_a_date_that_is_not_an_occurrence_is_400(db, world, client_signed_in) -> None:
    response = move(
        client_signed_in, world["algebra"], move_body(world["room_b"], original_date=TUE)
    )

    assert response.status_code == 400


def test_a_cancelled_activity_has_no_occurrence_to_move(db, world, client_signed_in) -> None:
    cancelled = world["weekly"]("Dropped", M2, day=1, status=Status.CANCELLED)

    response = move(client_signed_in, cancelled, move_body(world["room_b"]))

    assert response.status_code == 400


# --- a one-off ---------------------------------------------------------------------------------


def test_a_one_off_moves_to_a_new_one_off_and_the_old_one_is_cancelled(
    db, world, client_signed_in
) -> None:
    old = world["one_off"](
        "Colocviu", date(2026, 11, 24), M1, groups=(world["group_a"],), imported=True
    )

    response = move(
        client_signed_in,
        old,
        move_body(
            world["room_b"], original_date=TUE, new_date=WED, start_time="13:00", end_time="14:30"
        ),
    )

    assert response.status_code == 200, response.text
    db.refresh(old)
    assert old.status == Status.CANCELLED
    assert old.is_manually_modified is True
    new = db.get(Activity, uuid.UUID(response.json()["id"]))
    assert new.specific_date.isoformat() == WED
    assert new.start_time == time(13, 0)
    assert new.classroom_id == world["room_b"].id
    assert new.is_manually_modified is True
    assert new.name == "Colocviu"
    # The timetable is per week (TUE and WED are in the same week): check each day's entries.
    shown = timetable_titles(client_signed_in, TUE)
    assert not any(title == "Colocviu" and day == TUE for title, day, _ in shown)
    assert ("Colocviu", WED, "13:00") in shown
    assert str(world["room_a"].id) in free_room_ids(client_signed_in, TUE, "09:40", "11:10")


def test_a_one_off_must_be_moved_on_its_own_date(db, world, client_signed_in) -> None:
    old = world["one_off"]("Colocviu", date(2026, 11, 24), M1)

    response = move(client_signed_in, old, move_body(world["room_b"], original_date=MON))

    assert response.status_code == 400


# --- the checks -------------------------------------------------------------------------------


def test_a_new_date_before_today_is_400(db, world, client_signed_in) -> None:
    response = move(
        client_signed_in,
        world["algebra"],
        move_body(world["room_b"], original_date="2026-11-16", new_date="2026-11-19"),
    )

    assert response.status_code == 400


def test_times_must_be_whole_modules(db, world, client_signed_in) -> None:
    response = move(
        client_signed_in,
        world["algebra"],
        move_body(world["room_b"], start_time="09:00", end_time="10:30"),
    )

    assert response.status_code == 400


def test_a_room_that_is_not_bookable_is_400(db, world, client_signed_in) -> None:
    response = move(client_signed_in, world["algebra"], move_body(world["room_off"]))

    assert response.status_code == 400


def test_an_unknown_room_is_404(db, world, client_signed_in) -> None:
    body = move_body(world["room_b"], new_classroom_id=str(uuid.uuid4()))

    response = move(client_signed_in, world["algebra"], body)

    assert response.status_code == 404


def test_a_busy_room_is_409_with_the_reason(db, world, client_signed_in) -> None:
    world["one_off"](
        "Other exam", date(2026, 11, 24), M1, professor=world["other"], room=world["room_b"]
    )

    response = move(client_signed_in, world["algebra"], move_body(world["room_b"]))

    assert response.status_code == 409
    assert "room" in response.json()["detail"].lower()


def test_a_busy_professor_is_409(db, world, client_signed_in) -> None:
    world["weekly"]("Own class", M1, day=2, professor=world["ulbs_id"], room=world["room_b"])

    response = move(client_signed_in, world["algebra"], move_body(world["room_b"]))

    assert response.status_code == 409
    assert "Professor busy" in response.json()["detail"]


def test_a_busy_group_is_409_and_names_the_group(db, world, client_signed_in) -> None:
    world["weekly"](
        "Group class",
        M1,
        day=2,
        professor=world["other"],
        room=world["room_b"],
        groups=(world["group_a"],),
    )

    response = move(client_signed_in, world["algebra"], move_body(world["room_b"]))

    assert response.status_code == 409
    assert world["group_a"].name in response.json()["detail"]


def test_a_refused_move_changes_nothing(db, world, client_signed_in) -> None:
    world["one_off"](
        "Other exam", date(2026, 11, 24), M1, professor=world["other"], room=world["room_b"]
    )

    move(client_signed_in, world["algebra"], move_body(world["room_b"]))

    assert exceptions_of(db, world["algebra"]) == []


# --- who may move ----------------------------------------------------------------------------


def test_another_professors_activity_is_403(db, world, client_signed_in) -> None:
    theirs = world["weekly"]("Theirs", M2, professor=world["other"])

    response = move(client_signed_in, theirs, move_body(world["room_b"]))

    assert response.status_code == 403


def test_a_student_is_403(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-2", world["email"], Role.STUDENT)

    assert move(client, world["algebra"], move_body(world["room_b"])).status_code == 403


def test_an_unlinked_professor_is_403(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-3", "nobody.linked@ulbsibiu.ro", Role.PROFESSOR)

    assert move(client, world["algebra"], move_body(world["room_b"])).status_code == 403


def test_it_needs_a_sign_in(db, world) -> None:
    client = make_client(db)

    assert move(client, world["algebra"], move_body(world["room_b"])).status_code == 401


def test_an_unknown_activity_is_404(db, world, client_signed_in) -> None:
    response = client_signed_in.post(
        f"/api/professors/me/activities/{uuid.uuid4()}/move",
        json=move_body(world["room_b"]),
    )

    assert response.status_code == 404
