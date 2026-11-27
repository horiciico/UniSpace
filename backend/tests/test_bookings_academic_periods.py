"""POST /api/bookings follows the academic calendar (D-027, Task 4).

TEACHING (also when no period covers the date): whole modules. EXAM_SESSION: half-hour steps, 08:00
to 22:00, at least one hour. HOLIDAY: closed. The clock is fixed so no date is in the past.
"""

import uuid
from datetime import date, datetime, time

import pytest
from sqlalchemy.orm import Session

from app.models import (
    AcademicPeriod,
    AcademicPeriodType,
    Activity,
    ActivityType,
    Classroom,
    Priority,
    Role,
)
from app.planning import LOCAL_TZ
from tests.test_bookings_api import make_client, reset_overrides, sign_in  # noqa: F401

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=LOCAL_TZ)
TEACHING_DAY = "2026-12-07"
EXAM_DAY = "2026-12-14"
HOLIDAY_DAY = "2026-12-21"


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.routers.bookings.local_now", lambda: NOW)


@pytest.fixture
def room(db: Session) -> Classroom:
    tag = uuid.uuid4().hex[:8]
    row = Classroom(name=f"H-{tag}", capacity=30, external_id=f"h-{tag}")
    db.add(row)
    db.add_all(
        [
            AcademicPeriod(
                name="Sesiune",
                type=AcademicPeriodType.EXAM_SESSION,
                start_date=date(2026, 12, 10),
                end_date=date(2026, 12, 18),
            ),
            AcademicPeriod(
                name="Vacanta",
                type=AcademicPeriodType.HOLIDAY,
                start_date=date(2026, 12, 20),
                end_date=date(2027, 1, 3),
            ),
        ]
    )
    db.flush()
    return row


def body(room: Classroom, day: str, start: str, end: str) -> dict:
    return {
        "classroom_id": str(room.id),
        "specific_date": day,
        "start_time": start,
        "end_time": end,
        "title": "Study",
    }


@pytest.fixture
def student(db: Session, monkeypatch: pytest.MonkeyPatch):
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-ap-s", "ap.s@ulbsibiu.ro")
    return client


def test_teaching_keeps_the_module_boundaries(student, room: Classroom) -> None:
    assert (
        student.post("/api/bookings", json=body(room, TEACHING_DAY, "08:00", "09:30")).status_code
        == 201
    )
    r = student.post("/api/bookings", json=body(room, TEACHING_DAY, "10:00", "11:00"))
    assert r.status_code == 400


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("09:00", "10:00"),
        ("08:00", "22:00"),
        ("10:00", "13:00"),
        ("21:00", "22:00"),
        ("08:30", "10:00"),
        ("20:30", "22:00"),
    ],
)
def test_an_exam_session_accepts_half_hour_steps(student, room: Classroom, start, end) -> None:
    r = student.post("/api/bookings", json=body(room, EXAM_DAY, start, end))
    assert r.status_code == 201
    assert (r.json()["start_time"], r.json()["end_time"]) == (start, end)


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("09:40", "11:10"),  # a module, not half-hour steps
        ("08:30", "09:00"),
        ("10:00", "10:00"),  # under one hour
        ("11:00", "10:00"),
        ("07:00", "09:00"),  # before 08:00
        ("21:00", "23:00"),  # after 22:00
    ],
)
def test_an_exam_session_refuses_other_times(student, room: Classroom, start, end) -> None:
    assert student.post("/api/bookings", json=body(room, EXAM_DAY, start, end)).status_code == 400


def test_a_holiday_refuses_every_booking_with_a_clear_400(student, room: Classroom) -> None:
    for start, end in [("08:00", "09:30"), ("09:00", "10:00")]:
        r = student.post("/api/bookings", json=body(room, HOLIDAY_DAY, start, end))
        assert r.status_code == 400
        assert "holiday" in r.json()["detail"].lower()


def test_an_admin_is_also_refused_on_a_holiday(db: Session, room: Classroom, monkeypatch) -> None:
    admin = make_client(db)
    sign_in(db, admin, monkeypatch, "sub-ap-a", "ap.a@ulbsibiu.ro", role=Role.ADMIN)
    r = admin.post("/api/bookings", json=body(room, HOLIDAY_DAY, "09:00", "10:00"))
    assert r.status_code == 400


def test_an_exam_blocks_an_overlapping_hourly_booking(
    db: Session, student, room: Classroom
) -> None:
    db.add(
        Activity(
            name="Examen",
            type=ActivityType.EXAM,
            priority=Priority.EXAM,
            classroom_id=room.id,
            day_of_week=1,
            specific_date=date(2026, 12, 14),
            start_time=time(10, 0),
            end_time=time(13, 0),
            external_id=f"x-{uuid.uuid4().hex[:8]}",
        )
    )
    db.flush()

    clash = student.post("/api/bookings", json=body(room, EXAM_DAY, "12:00", "14:00"))
    after = student.post("/api/bookings", json=body(room, EXAM_DAY, "13:00", "14:00"))

    assert clash.status_code == 409
    assert "Examen" in clash.json()["detail"]
    assert after.status_code == 201


def test_an_approved_hourly_booking_blocks_an_overlapping_one_in_an_exam_session(
    db: Session, student, room: Classroom, monkeypatch
) -> None:
    admin = make_client(db)
    sign_in(db, admin, monkeypatch, "sub-ap-a2", "ap.a2@ulbsibiu.ro", role=Role.ADMIN)
    assert (
        admin.post("/api/bookings", json=body(room, EXAM_DAY, "10:00", "13:00")).status_code == 201
    )

    r = student.post("/api/bookings", json=body(room, EXAM_DAY, "12:00", "14:00"))

    assert r.status_code == 409
