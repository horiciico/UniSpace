"""The cascading availability of a day for a professor and groups.

Endpoint: GET /api/professors/me/availability.

Modules are the university's 90-minute modules (planning.MODULES). A module is unavailable when the
professor or any requested group has an occurrence in it (planning.occurrences: parity, exceptions,
cancellations, moves). `exclude_activity_id` drops that activity's occurrence on `date` only.
Free classrooms: bookable rooms with no occurrence and no approved booking in the module.

Week 7 (2026-11-16, Monday) is ODD; 2026-11-23 (Monday) is EVEN. The unit starts 2026-10-05.
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
    Booking,
    BookingStatus,
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
from app.planning import MODULES, hhmm

MON = "2026-11-16"  # Monday, week 7 (ODD)
MON_EVEN = "2026-11-23"  # Monday, week 8 (EVEN)
TUE = "2026-11-17"

# Module start/end times as the API prints them.
M0 = (time(8, 0), time(9, 30))
M1 = (time(9, 40), time(11, 10))
M2 = (time(11, 20), time(12, 50))


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
    faculty = Faculty(code=f"v{tag}", name="Facultatea de Test")
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

    def weekly(
        name: str,
        span: tuple[time, time],
        *,
        professor: uuid.UUID | None = None,
        room: Classroom = room_a,
        parity: Parity = Parity.ALL,
        groups: tuple[StudentGroup, ...] = (),
        status: Status = Status.APPROVED,
    ) -> Activity:
        activity = Activity(
            name=name,
            type=ActivityType.COURSE,
            priority=Priority.COURSE,
            classroom_id=room.id,
            day_of_week=1,
            start_time=span[0],
            end_time=span[1],
            parity=parity,
            planning_time_unit_id=unit.id,
            external_id=f"{name}-{tag}-{uuid.uuid4().hex[:6]}",
            professor_id=professor or uuid.uuid4(),
            professor_name=f"Someone {tag}",
            status=status,
        )
        db.add(activity)
        db.flush()
        for group in groups:
            db.add(ActivityGroup(activity_id=activity.id, group_id=group.id))
        db.flush()
        return activity

    def one_off(
        name: str,
        on: date,
        span: tuple[time, time],
        *,
        professor: uuid.UUID | None = None,
        room: Classroom = room_a,
    ) -> Activity:
        activity = Activity(
            name=name,
            type=ActivityType.EXAM,
            priority=Priority.EXAM,
            classroom_id=room.id,
            day_of_week=on.isoweekday(),
            start_time=span[0],
            end_time=span[1],
            parity=Parity.ALL,
            specific_date=on,
            professor_id=professor or uuid.uuid4(),
            professor_name=f"Someone {tag}",
        )
        db.add(activity)
        db.flush()
        return activity

    return {
        "email": email,
        "ulbs_id": ulbs_id,
        "room_a": room_a,
        "room_b": room_b,
        "room_off": room_off,
        "group_a": group_a,
        "group_b": group_b,
        "other": uuid.uuid4(),
        "weekly": weekly,
        "one_off": one_off,
        "db": db,
    }


def get_day(client: TestClient, day: str, **params) -> dict:
    response = client.get("/api/professors/me/availability", params={"date": day, **params})
    assert response.status_code == 200, response.text
    return response.json()


def module_at(body: dict, start: time) -> dict:
    return next(m for m in body["modules"] if m["start_time"] == hhmm(start))


def room_ids(module: dict) -> set[str]:
    return {room["id"] for room in module["free_classrooms"]}


def signed_in_professor(db, client, monkeypatch, world) -> None:
    sign_in(db, client, monkeypatch, "sub-1", world["email"], Role.PROFESSOR)


# --- the grid -------------------------------------------------------------------------------


def test_the_day_has_the_eight_planning_modules(db, world, monkeypatch) -> None:
    client = make_client(db)
    signed_in_professor(db, client, monkeypatch, world)

    body = get_day(client, MON)

    assert body["date"] == MON
    assert [(m["start_time"], m["end_time"]) for m in body["modules"]] == [
        (hhmm(start), hhmm(end)) for start, end in MODULES
    ]
    assert body["modules"][0]["start_time"] == "08:00"
    assert body["modules"][-1]["end_time"] == "21:10"


def test_an_empty_day_has_every_module_available_and_every_room_free(
    db, world, monkeypatch
) -> None:
    client = make_client(db)
    signed_in_professor(db, client, monkeypatch, world)

    body = get_day(client, MON)

    for module in body["modules"]:
        assert module["available"] is True
        assert module["conflict_reason"] is None
        assert {world["room_a"].id, world["room_b"].id} <= {
            uuid.UUID(room_id) for room_id in room_ids(module)
        }


# --- the professor and the groups -----------------------------------------------------------


def test_the_professors_own_class_makes_its_module_unavailable(db, world, monkeypatch) -> None:
    client = make_client(db)
    world["weekly"]("Algebra", M0, professor=world["ulbs_id"])
    signed_in_professor(db, client, monkeypatch, world)

    body = get_day(client, MON)

    busy = module_at(body, M0[0])
    assert busy["available"] is False
    assert "Algebra" in busy["conflict_reason"]
    assert "Professor" in busy["conflict_reason"]
    assert module_at(body, M1[0])["available"] is True


def test_another_professors_class_does_not_block_me(db, world, monkeypatch) -> None:
    client = make_client(db)
    world["weekly"]("Other lecture", M0, professor=world["other"])
    signed_in_professor(db, client, monkeypatch, world)

    assert module_at(get_day(client, MON), M0[0])["available"] is True


def test_a_busy_group_makes_the_module_unavailable_and_names_the_group(
    db, world, monkeypatch
) -> None:
    client = make_client(db)
    world["weekly"]("Lecture", M1, professor=world["other"], groups=(world["group_a"],))
    signed_in_professor(db, client, monkeypatch, world)

    body = get_day(client, MON, group_ids=[str(world["group_a"].id)])

    busy = module_at(body, M1[0])
    assert busy["available"] is False
    assert world["group_a"].name in busy["conflict_reason"]
    assert module_at(body, M0[0])["available"] is True


def test_a_group_that_is_not_busy_does_not_block(db, world, monkeypatch) -> None:
    client = make_client(db)
    world["weekly"]("Lecture", M1, professor=world["other"], groups=(world["group_a"],))
    signed_in_professor(db, client, monkeypatch, world)

    body = get_day(client, MON, group_ids=[str(world["group_b"].id)])

    assert module_at(body, M1[0])["available"] is True


def test_any_requested_busy_group_blocks_the_module(db, world, monkeypatch) -> None:
    client = make_client(db)
    world["weekly"]("Lecture", M1, professor=world["other"], groups=(world["group_a"],))
    signed_in_professor(db, client, monkeypatch, world)

    body = get_day(
        client,
        MON,
        group_ids=[str(world["group_b"].id), str(world["group_a"].id)],
    )

    busy = module_at(body, M1[0])
    assert busy["available"] is False
    assert world["group_a"].name in busy["conflict_reason"]
    assert world["group_b"].name not in busy["conflict_reason"]


def test_an_unknown_group_is_404(db, world, monkeypatch) -> None:
    client = make_client(db)
    signed_in_professor(db, client, monkeypatch, world)

    response = client.get(
        "/api/professors/me/availability",
        params={"date": MON, "group_ids": [str(uuid.uuid4())]},
    )

    assert response.status_code == 404


# --- parity, one-offs, exceptions, exclusion ------------------------------------------------


def test_parity_is_respected(db, world, monkeypatch) -> None:
    client = make_client(db)
    world["weekly"]("Odd course", M0, professor=world["ulbs_id"], parity=Parity.ODD)
    signed_in_professor(db, client, monkeypatch, world)

    assert module_at(get_day(client, MON), M0[0])["available"] is False
    assert module_at(get_day(client, MON_EVEN), M0[0])["available"] is True


def test_a_one_off_blocks_only_its_date(db, world, monkeypatch) -> None:
    client = make_client(db)
    world["one_off"]("Colocviu", date(2026, 11, 16), M0, professor=world["ulbs_id"])
    signed_in_professor(db, client, monkeypatch, world)

    assert module_at(get_day(client, MON), M0[0])["available"] is False
    assert module_at(get_day(client, MON_EVEN), M0[0])["available"] is True


def test_a_cancelled_occurrence_does_not_block(db, world, monkeypatch) -> None:
    client = make_client(db)
    activity = world["weekly"]("Cancelled", M0, professor=world["ulbs_id"])
    db.add(
        ActivityException(
            activity_id=activity.id, original_date=date(2026, 11, 16), is_cancelled=True
        )
    )
    db.flush()
    signed_in_professor(db, client, monkeypatch, world)

    assert module_at(get_day(client, MON), M0[0])["available"] is True


def test_a_class_moved_away_frees_its_old_module_and_busies_the_new_one(
    db, world, monkeypatch
) -> None:
    client = make_client(db)
    activity = world["weekly"]("Moved", M0, professor=world["ulbs_id"])
    db.add(
        ActivityException(
            activity_id=activity.id,
            original_date=date(2026, 11, 16),
            new_date=date(2026, 11, 17),
            new_start_time=M1[0],
            new_end_time=M1[1],
        )
    )
    db.flush()
    signed_in_professor(db, client, monkeypatch, world)

    assert module_at(get_day(client, MON), M0[0])["available"] is True
    moved_to = module_at(get_day(client, TUE), M1[0])
    assert moved_to["available"] is False
    assert "Moved" in moved_to["conflict_reason"]


def test_exclude_activity_id_ignores_its_own_occurrence_for_professor_and_group(
    db, world, monkeypatch
) -> None:
    client = make_client(db)
    mine = world["weekly"]("Mine", M0, professor=world["ulbs_id"], groups=(world["group_a"],))
    signed_in_professor(db, client, monkeypatch, world)
    group = [str(world["group_a"].id)]

    before = get_day(client, MON, group_ids=group)
    after = get_day(client, MON, group_ids=group, exclude_activity_id=str(mine.id))

    assert module_at(before, M0[0])["available"] is False
    assert module_at(after, M0[0])["available"] is True


def test_exclude_applies_only_to_the_requested_date(db, world, monkeypatch) -> None:
    client = make_client(db)
    mine = world["weekly"]("Weekly", M0, professor=world["ulbs_id"])
    signed_in_professor(db, client, monkeypatch, world)

    excluded_day = get_day(client, MON, exclude_activity_id=str(mine.id))
    other_day = get_day(client, MON_EVEN)

    assert module_at(excluded_day, M0[0])["available"] is True
    # Excluding it on MON does not touch its occurrence on MON_EVEN, which is still busy.
    assert module_at(other_day, M0[0])["available"] is False


# --- free classrooms ------------------------------------------------------------------------


def test_a_room_in_use_is_not_free_in_its_module_only(db, world, monkeypatch) -> None:
    client = make_client(db)
    world["weekly"]("Lab", M0, professor=world["other"], room=world["room_a"])
    signed_in_professor(db, client, monkeypatch, world)

    body = get_day(client, MON)

    room_a = str(world["room_a"].id)
    assert room_a not in room_ids(module_at(body, M0[0]))
    assert room_a in room_ids(module_at(body, M1[0]))
    assert str(world["room_b"].id) in room_ids(module_at(body, M0[0]))


def test_an_approved_booking_takes_a_room_and_a_pending_one_does_not(
    db, world, monkeypatch
) -> None:
    client = make_client(db)
    student = User(email=f"s.{uuid.uuid4().hex[:8]}@ulbsibiu.ro", name="Student", role=Role.STUDENT)
    db.add(student)
    db.flush()
    db.add_all(
        [
            Booking(
                user_id=student.id,
                classroom_id=world["room_b"].id,
                specific_date=date(2026, 11, 16),
                start_time=M2[0],
                end_time=M2[1],
                title="Approved",
                status=BookingStatus.APPROVED,
            ),
            Booking(
                user_id=student.id,
                classroom_id=world["room_a"].id,
                specific_date=date(2026, 11, 16),
                start_time=M2[0],
                end_time=M2[1],
                title="Pending",
                status=BookingStatus.PENDING,
            ),
        ]
    )
    db.flush()
    signed_in_professor(db, client, monkeypatch, world)

    module = module_at(get_day(client, MON), M2[0])

    assert str(world["room_b"].id) not in room_ids(module)
    assert str(world["room_a"].id) in room_ids(module)


def test_rooms_that_are_not_bookable_are_never_listed(db, world, monkeypatch) -> None:
    client = make_client(db)
    signed_in_professor(db, client, monkeypatch, world)

    body = get_day(client, MON)

    for module in body["modules"]:
        assert str(world["room_off"].id) not in room_ids(module)


def test_a_cancelled_occurrence_frees_its_room(db, world, monkeypatch) -> None:
    client = make_client(db)
    activity = world["weekly"]("Cancelled", M0, professor=world["other"], room=world["room_a"])
    db.add(
        ActivityException(
            activity_id=activity.id, original_date=date(2026, 11, 16), is_cancelled=True
        )
    )
    db.flush()
    signed_in_professor(db, client, monkeypatch, world)

    assert str(world["room_a"].id) in room_ids(module_at(get_day(client, MON), M0[0]))


def test_excluding_an_activity_frees_its_room(db, world, monkeypatch) -> None:
    client = make_client(db)
    mine = world["weekly"]("Mine", M0, professor=world["ulbs_id"], room=world["room_a"])
    signed_in_professor(db, client, monkeypatch, world)

    before = get_day(client, MON)
    after = get_day(client, MON, exclude_activity_id=str(mine.id))

    assert str(world["room_a"].id) not in room_ids(module_at(before, M0[0]))
    assert str(world["room_a"].id) in room_ids(module_at(after, M0[0]))


def test_a_free_room_has_the_room_fields(db, world, monkeypatch) -> None:
    client = make_client(db)
    signed_in_professor(db, client, monkeypatch, world)

    room = module_at(get_day(client, MON), M0[0])["free_classrooms"][0]

    assert set(room) == {"id", "name", "capacity", "has_projector", "is_field_verified"}


# --- who may ask ---------------------------------------------------------------------------


def test_a_student_is_refused(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-2", world["email"], Role.STUDENT)

    assert client.get("/api/professors/me/availability", params={"date": MON}).status_code == 403


def test_a_professor_with_no_row_is_refused(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-3", "nobody.linked@ulbsibiu.ro", Role.PROFESSOR)

    assert client.get("/api/professors/me/availability", params={"date": MON}).status_code == 403


def test_it_needs_a_sign_in(db, world) -> None:
    client = make_client(db)

    assert client.get("/api/professors/me/availability", params={"date": MON}).status_code == 401


def test_a_missing_date_is_422(db, world, monkeypatch) -> None:
    client = make_client(db)
    signed_in_professor(db, client, monkeypatch, world)

    assert client.get("/api/professors/me/availability").status_code == 422
