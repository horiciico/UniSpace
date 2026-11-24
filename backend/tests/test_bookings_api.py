"""Room bookings: POST /api/bookings, GET /api/bookings/my, DELETE /api/bookings/{id}, and the
approved bookings that hide a room from GET /api/classrooms/free.

The clock is fixed (NOW) so the past-time rule does not depend on the real date.
DB tests: the endpoints run against the rolled-back `db` fixture (PATTERN-005, PATTERN-006).
Week numbers: the planning unit starts on Monday 2026-10-05, so
  2026-12-14 is week 11 (ODD), 2026-12-21 is week 12 (EVEN).
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
from app.models import (
    Activity,
    ActivityException,
    ActivityType,
    Booking,
    BookingStatus,
    Classroom,
    Faculty,
    Parity,
    PlanningTimeUnit,
    PlanningUnitType,
    Priority,
    Role,
    Status,
    User,
)
from app.planning import LOCAL_TZ

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=LOCAL_TZ)
MON_ODD = "2026-12-14"  # week 11: the odd-week course runs
MON_EVEN = "2026-12-21"  # week 12: it does not


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.routers.bookings.local_now", lambda: NOW)


def make_client(db: Session) -> TestClient:
    """A client with its own session cookie, so several users can be signed in at once."""
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


@pytest.fixture(autouse=True)
def reset_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def world(db: Session) -> dict:
    """One faculty, a bookable room and a room that is not bookable.

    In the room: a course Monday 10:00-12:00 in odd weeks; a course Monday 16:00-17:00 whose
    occurrence on MON_ODD is cancelled by an exception; an activity with status CANCELLED on
    Tuesday 13:00-14:30. (The free-room search does not skip cancelled occurrences yet, see Q-017,
    so the cancelled ones sit on days and times the other free-room tests do not use.)
    """
    tag = uuid.uuid4().hex[:8]
    faculty = Faculty(code=f"t{tag}", name="Facultatea de Test")
    db.add(faculty)
    db.flush()
    unit = PlanningTimeUnit(
        faculty_id=faculty.id, external_id=1, year=2026, name="Semestrul 1",
        type=PlanningUnitType.SEMESTER, start_date=date(2026, 10, 5), end_date=date(2027, 1, 31),
    )
    db.add(unit)
    db.flush()
    room = Classroom(name=f"A-{tag}", capacity=30, faculty_id=faculty.id, external_id=f"a-{tag}")
    closed = Classroom(name=f"C-{tag}", capacity=50, faculty_id=faculty.id, is_bookable=False,
                       external_id=f"c-{tag}")
    campus = Classroom(name=f"P-{tag}", capacity=20, faculty_id=None, external_id=f"p-{tag}")
    db.add_all([room, closed, campus])
    db.flush()

    def activity(name: str, **kw) -> Activity:
        values = dict(
            name=name, type=ActivityType.COURSE, priority=Priority.COURSE, classroom_id=room.id,
            day_of_week=1, parity=Parity.ALL, planning_time_unit_id=unit.id, external_id=f"{name}-{tag}",
        )
        values.update(kw)
        return Activity(**values)

    course = activity("odd", start_time=time(10, 0), end_time=time(12, 0), parity=Parity.ODD)
    cancelled = activity("cancelled", day_of_week=2, start_time=time(13, 0), end_time=time(14, 30),
                         status=Status.CANCELLED)
    excepted = activity("excepted", start_time=time(16, 0), end_time=time(17, 0))
    db.add_all([course, cancelled, excepted])
    db.flush()
    db.add(ActivityException(activity_id=excepted.id, original_date=date(2026, 12, 14), is_cancelled=True))
    db.flush()
    return {"faculty": faculty, "room": room, "closed": closed, "campus": campus, "unit": unit, "tag": tag}


def body(world: dict, **kw) -> dict:
    values = {
        "classroom_id": str(world["room"].id), "specific_date": MON_ODD,
        "start_time": "08:00", "end_time": "09:30", "title": "Club meeting",
    }
    values.update(kw)
    return values


# --- POST /api/bookings ------------------------------------------------------------------

def test_a_student_books_a_free_room_and_it_is_pending(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-s1", "student.one@ulbsibiu.ro")

    r = client.post("/api/bookings", json=body(world))

    assert r.status_code == 201
    created = r.json()
    assert created["status"] == "pending"
    assert created["title"] == "Club meeting"
    assert created["specific_date"] == MON_ODD
    assert created["start_time"] == "08:00" and created["end_time"] == "09:30"


def test_every_signed_in_role_can_book(db, world, monkeypatch) -> None:
    for role, sub in [(Role.STUDENT_ORG, "sub-o"), (Role.PROFESSOR, "sub-p")]:
        client = make_client(db)
        sign_in(db, client, monkeypatch, sub, f"{sub}@ulbsibiu.ro", role=role)
        assert client.post("/api/bookings", json=body(world)).status_code == 201


def test_an_admin_booking_is_approved_at_once(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-a", "admin.one@ulbsibiu.ro", role=Role.ADMIN)

    r = client.post("/api/bookings", json=body(world))

    assert r.status_code == 201
    assert r.json()["status"] == "approved"


def test_booking_needs_a_sign_in(db, world) -> None:
    client = make_client(db)

    assert client.post("/api/bookings", json=body(world)).status_code == 401


def test_an_unknown_room_is_404(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-s2", "student.two@ulbsibiu.ro")

    r = client.post("/api/bookings", json=body(world, classroom_id=str(uuid.uuid4())))

    assert r.status_code == 404


def test_a_room_that_is_not_bookable_is_400(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-s3", "student.three@ulbsibiu.ro")

    r = client.post("/api/bookings", json=body(world, classroom_id=str(world["closed"].id)))

    assert r.status_code == 400


@pytest.mark.parametrize("times", [
    {"start_time": "09:00", "end_time": "10:00"},  # not a module start
    {"start_time": "08:00", "end_time": "09:00"},  # not a module end
    {"start_time": "10:00", "end_time": "09:30"},  # end before start
    {"start_time": "09:40", "end_time": "09:40"},  # empty
])
def test_times_must_be_whole_modules_in_order(db, world, monkeypatch, times) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-s4", "student.four@ulbsibiu.ro")

    r = client.post("/api/bookings", json=body(world, **times))

    assert r.status_code == 400


def test_a_past_date_is_400(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-s5", "student.five@ulbsibiu.ro")

    r = client.post("/api/bookings", json=body(world, specific_date="2026-11-23"))

    assert r.status_code == 400


def test_a_start_earlier_today_than_now_is_400(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-s6", "student.six@ulbsibiu.ro")

    r = client.post("/api/bookings", json=body(world, specific_date="2026-11-24",
                                              start_time="08:00", end_time="09:30"))

    assert r.status_code == 400  # NOW is 12:00 that day


def test_a_recurring_course_blocks_an_overlapping_booking_with_409(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-s7", "student.seven@ulbsibiu.ro")

    r = client.post("/api/bookings", json=body(world, start_time="09:40", end_time="11:10"))

    assert r.status_code == 409
    assert "10:00" in r.json()["detail"]  # the message names the clash


def test_a_recurring_course_does_not_block_in_its_off_week(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-s8", "student.eight@ulbsibiu.ro")

    r = client.post("/api/bookings", json=body(world, specific_date=MON_EVEN, start_time="09:40",
                                              end_time="11:10"))

    assert r.status_code == 201


def test_a_back_to_back_booking_does_not_clash(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-s9", "student.nine@ulbsibiu.ro")

    r = client.post("/api/bookings", json=body(world, start_time="08:00", end_time="09:30"))

    assert r.status_code == 201  # the course starts at 10:00


def test_a_cancelled_activity_or_occurrence_does_not_block(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-s10", "student.ten@ulbsibiu.ro")

    on_tuesday = "2026-12-15"  # the activity with status CANCELLED runs here, 13:00-14:30
    cancelled_activity = client.post("/api/bookings", json=body(world, specific_date=on_tuesday,
                                                               start_time="13:00", end_time="14:30"))
    cancelled_occurrence = client.post("/api/bookings", json=body(world, start_time="16:20", end_time="17:50"))

    # 16:00-17:00 on MON_ODD is cancelled by an exception, so the booking there is allowed.
    assert cancelled_activity.status_code == 201
    assert cancelled_occurrence.status_code == 201


def test_an_approved_booking_blocks_an_overlapping_booking_with_409(db, world, monkeypatch) -> None:
    admin = make_client(db)
    sign_in(db, admin, monkeypatch, "sub-adm", "admin.two@ulbsibiu.ro", role=Role.ADMIN)
    assert admin.post("/api/bookings", json=body(world, start_time="13:00", end_time="14:30")).status_code == 201

    student = make_client(db)
    sign_in(db, student, monkeypatch, "sub-s11", "student.eleven@ulbsibiu.ro")
    r = student.post("/api/bookings", json=body(world, start_time="13:00", end_time="14:30"))

    assert r.status_code == 409


def test_an_overlapping_pending_booking_is_allowed(db, world, monkeypatch) -> None:
    first = make_client(db)
    sign_in(db, first, monkeypatch, "sub-s12", "student.twelve@ulbsibiu.ro")
    assert first.post("/api/bookings", json=body(world, start_time="13:00", end_time="14:30")).status_code == 201

    second = make_client(db)
    sign_in(db, second, monkeypatch, "sub-s13", "student.thirteen@ulbsibiu.ro")
    r = second.post("/api/bookings", json=body(world, start_time="13:00", end_time="14:30"))

    assert r.status_code == 201


def test_a_cancelled_booking_does_not_block(db, world, monkeypatch) -> None:
    student = make_client(db)
    sign_in(db, student, monkeypatch, "sub-s14", "student.fourteen@ulbsibiu.ro")
    first = student.post("/api/bookings", json=body(world, start_time="13:00", end_time="14:30")).json()
    assert student.delete(f"/api/bookings/{first['id']}").status_code == 200

    admin = make_client(db)
    sign_in(db, admin, monkeypatch, "sub-adm2", "admin.three@ulbsibiu.ro", role=Role.ADMIN)
    assert admin.post("/api/bookings", json=body(world, start_time="13:00", end_time="14:30")).status_code == 201


# --- GET /api/bookings/my ---------------------------------------------------------------

def test_my_bookings_lists_only_mine_with_room_and_faculty(db, world, monkeypatch) -> None:
    mine = make_client(db)
    sign_in(db, mine, monkeypatch, "sub-m1", "mine@ulbsibiu.ro")
    mine.post("/api/bookings", json=body(world, specific_date="2026-12-15", start_time="08:00", end_time="09:30"))

    other = make_client(db)
    sign_in(db, other, monkeypatch, "sub-m2", "other@ulbsibiu.ro")
    other.post("/api/bookings", json=body(world, start_time="13:00", end_time="14:30"))

    rows = mine.get("/api/bookings/my").json()

    assert len(rows) == 1
    row = rows[0]
    assert row["title"] == "Club meeting"
    assert row["room_name"] == world["room"].name
    assert row["faculty_name"] == "Facultatea de Test"
    assert row["status"] == "pending"
    assert row["specific_date"] == "2026-12-15"


def test_my_bookings_puts_upcoming_first_then_past(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-m3", "order@ulbsibiu.ro")
    user = db.scalar(select(User).where(User.email == "order@ulbsibiu.ro"))
    room = world["room"].id
    db.add_all([
        Booking(user_id=user.id, classroom_id=room, specific_date=date(2026, 11, 20), start_time=time(8, 0),
                end_time=time(9, 30), title="past"),
        Booking(user_id=user.id, classroom_id=room, specific_date=date(2026, 12, 20), start_time=time(13, 0),
                end_time=time(14, 30), title="later"),
        Booking(user_id=user.id, classroom_id=room, specific_date=date(2026, 12, 1), start_time=time(9, 40),
                end_time=time(11, 10), title="sooner"),
    ])
    db.flush()

    titles = [row["title"] for row in client.get("/api/bookings/my").json()]

    assert titles == ["sooner", "later", "past"]


def test_my_bookings_needs_a_sign_in(db) -> None:
    assert make_client(db).get("/api/bookings/my").status_code == 401


# --- DELETE /api/bookings/{id} ----------------------------------------------------------

def test_the_owner_cancels_a_pending_booking(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-d1", "cancel.me@ulbsibiu.ro")
    created = client.post("/api/bookings", json=body(world)).json()

    r = client.delete(f"/api/bookings/{created['id']}")

    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
    row = db.get(Booking, uuid.UUID(created["id"]))
    assert row is not None and row.status.value == "cancelled"  # the row is kept


def test_an_approved_booking_cannot_be_cancelled_by_the_student(db, world, monkeypatch) -> None:
    student = make_client(db)
    sign_in(db, student, monkeypatch, "sub-d2", "locked@ulbsibiu.ro")
    created = student.post("/api/bookings", json=body(world)).json()
    # Approval is an admin action that comes later; here the row is approved directly.
    db.get(Booking, uuid.UUID(created["id"])).status = BookingStatus.APPROVED
    db.flush()

    assert student.delete(f"/api/bookings/{created['id']}").status_code == 409


def test_an_admin_who_is_not_the_owner_cannot_cancel_a_booking(db, world, monkeypatch) -> None:
    student = make_client(db)
    sign_in(db, student, monkeypatch, "sub-d2c", "owned@ulbsibiu.ro")
    created = student.post("/api/bookings", json=body(world)).json()

    admin = make_client(db)
    sign_in(db, admin, monkeypatch, "sub-d2d", "admin.four@ulbsibiu.ro", role=Role.ADMIN)

    assert admin.delete(f"/api/bookings/{created['id']}").status_code == 403


def test_a_booking_that_is_already_cancelled_is_409(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-d3", "twice@ulbsibiu.ro")
    created = client.post("/api/bookings", json=body(world)).json()
    assert client.delete(f"/api/bookings/{created['id']}").status_code == 200

    assert client.delete(f"/api/bookings/{created['id']}").status_code == 409


def test_another_users_booking_cannot_be_cancelled(db, world, monkeypatch) -> None:
    owner = make_client(db)
    sign_in(db, owner, monkeypatch, "sub-d4", "owner@ulbsibiu.ro")
    created = owner.post("/api/bookings", json=body(world)).json()

    intruder = make_client(db)
    sign_in(db, intruder, monkeypatch, "sub-d5", "intruder@ulbsibiu.ro")

    assert intruder.delete(f"/api/bookings/{created['id']}").status_code == 403


def test_cancelling_an_unknown_booking_is_404(db, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-d6", "nobody@ulbsibiu.ro")

    assert client.delete(f"/api/bookings/{uuid.uuid4()}").status_code == 404


# --- GET /api/classrooms/free and bookings ----------------------------------------------

def test_approved_bookings_hide_a_room_from_free_now_but_pending_ones_do_not(db, world, monkeypatch) -> None:
    params = {"date": MON_ODD, "start_time": "13:00", "faculty_id": str(world["faculty"].id)}

    student = make_client(db)
    sign_in(db, student, monkeypatch, "sub-f1", "free.student@ulbsibiu.ro")
    student.post("/api/bookings", json=body(world, start_time="13:00", end_time="14:30"))
    with_pending = student.get("/api/classrooms/free", params=params).json()
    assert [row["id"] for row in with_pending] == [str(world["room"].id)]

    admin = make_client(db)
    sign_in(db, admin, monkeypatch, "sub-f2", "free.admin@ulbsibiu.ro", role=Role.ADMIN)
    admin.post("/api/bookings", json=body(world, start_time="13:00", end_time="14:30"))
    with_approved = student.get("/api/classrooms/free", params=params).json()
    assert with_approved == []


def test_free_now_reports_the_searched_window(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-f3", "window@ulbsibiu.ro")

    rows = client.get("/api/classrooms/free", params={
        "date": MON_ODD, "start_time": "13:00", "end_time": "14:30", "faculty_id": str(world["faculty"].id),
    }).json()

    assert rows and rows[0]["start_time"] == "13:00" and rows[0]["end_time"] == "14:30"
    # Q-017: the course at 16:00 is cancelled on this date by an exception, so it no longer blocks the room.
    assert rows[0]["free_until"] == "21:10"


def test_a_room_with_no_faculty_has_a_null_faculty_name(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-m4", "campus@ulbsibiu.ro")
    client.post("/api/bookings", json=body(world, classroom_id=str(world["campus"].id),
                                          specific_date="2026-12-15", start_time="08:00", end_time="09:30"))

    row = client.get("/api/bookings/my").json()[0]

    assert row["room_name"] == world["campus"].name
    assert row["faculty_name"] is None  # the frontend shows "Campus" (D-012)


def test_a_moved_course_blocks_its_new_time_and_frees_its_old_one(db, world, monkeypatch) -> None:
    # A course on Thursday 09:40-11:10, moved on that week to Friday 13:00-14:30 (Q-017).
    thursday, friday = "2026-12-17", "2026-12-18"
    course = Activity(
        name="Moved", type=ActivityType.COURSE, priority=Priority.COURSE, classroom_id=world["room"].id,
        day_of_week=4, start_time=time(9, 40), end_time=time(11, 10), parity=Parity.ALL,
        planning_time_unit_id=world["unit"].id, external_id=f"moved-{world['tag']}",
    )
    db.add(course)
    db.flush()
    db.add(ActivityException(activity_id=course.id, original_date=date(2026, 12, 17), new_date=date(2026, 12, 18),
                             new_start_time=time(13, 0), new_end_time=time(14, 30)))
    db.flush()

    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-mv", "moved@ulbsibiu.ro")

    old_slot = client.post("/api/bookings", json=body(world, specific_date=thursday,
                                                     start_time="09:40", end_time="11:10"))
    new_slot = client.post("/api/bookings", json=body(world, specific_date=friday,
                                                     start_time="13:00", end_time="14:30"))

    assert old_slot.status_code == 201
    assert new_slot.status_code == 409


def test_an_approved_booking_shows_in_the_room_timetable(db, world, monkeypatch) -> None:
    client = make_client(db)
    user = sign_in(db, client, monkeypatch, "sub-tt", "timetable.booking@ulbsibiu.ro")
    room = world["room"].id
    db.add_all([
        Booking(user_id=user.id, classroom_id=room, specific_date=date(2026, 12, 14), start_time=time(13, 0),
                end_time=time(14, 30), title="Approved gala", status=BookingStatus.APPROVED),
        Booking(user_id=user.id, classroom_id=room, specific_date=date(2026, 12, 14), start_time=time(15, 0),
                end_time=time(16, 30), title="Still pending", status=BookingStatus.PENDING),
        Booking(user_id=user.id, classroom_id=room, specific_date=date(2026, 12, 14), start_time=time(9, 40),
                end_time=time(11, 10), title="Cancelled", status=BookingStatus.CANCELLED),
    ])
    db.flush()

    data = make_client(db).get("/api/schedule", params={"room_id": str(room), "date": MON_ODD}).json()

    booked = [item for item in data["items"] if item["activity_type"] == "BOOKING"]
    assert [(i["title"], i["date"], i["day_of_week"], i["start_time"], i["end_time"]) for i in booked] == [
        ("Approved gala", MON_ODD, 1, "13:00", "14:30"),
    ]
    assert booked[0]["room_id"] == str(room)
    assert booked[0]["is_recurring"] is False
    assert booked[0]["groups"] == [] and booked[0]["professor"] is None
    assert "timetable.booking@ulbsibiu.ro" not in str(booked[0])  # no one's identity on the timetable


def test_bookings_are_not_added_to_a_group_or_professor_timetable(db, world, monkeypatch) -> None:
    client = make_client(db)
    user = sign_in(db, client, monkeypatch, "sub-tt2", "timetable.booking2@ulbsibiu.ro")
    db.add(Booking(user_id=user.id, classroom_id=world["room"].id, specific_date=date(2026, 12, 14),
                   start_time=time(13, 0), end_time=time(14, 30), title="Gala", status=BookingStatus.APPROVED))
    db.flush()

    data = make_client(db).get("/api/schedule", params={"professor": "Fara Profesor", "date": MON_ODD}).json()

    assert all(item["activity_type"] != "BOOKING" for item in data["items"])

