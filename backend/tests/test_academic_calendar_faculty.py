"""The academic calendar per faculty (D-028): a faculty's own periods, with the all-faculties
periods as the default.

DB tests: they need PostgreSQL (compose `db`); see conftest.py.
"""

import uuid
from datetime import date, datetime, time

import pytest
from sqlalchemy.orm import Session

from app.academic_calendar import find_overlapping_period, get_period_type_for_date
from app.models import (
    AcademicPeriod,
    AcademicPeriodType,
    Activity,
    ActivityType,
    Classroom,
    Faculty,
    Parity,
    PlanningTimeUnit,
    PlanningUnitType,
    Priority,
    Role,
)
from app.planning import LOCAL_TZ, occurrences
from tests.test_academic_periods_api import URL, admin, body, make_client  # noqa: F401
from tests.test_bookings_api import reset_overrides, sign_in  # noqa: F401
from tests.test_professor_timetable import sign_in as sign_in_as
from tests.test_professor_timetable import world  # noqa: F401

T, E, H = (
    AcademicPeriodType.TEACHING,
    AcademicPeriodType.EXAM_SESSION,
    AcademicPeriodType.HOLIDAY,
)
MONDAY = date(2031, 12, 15)


def make_faculty(db: Session, name: str) -> Faculty:
    row = Faculty(code=f"f{uuid.uuid4().hex[:8]}", name=name)
    db.add(row)
    db.flush()
    return row


def period(db: Session, kind, start: date, end: date, faculty: Faculty | None = None):
    row = AcademicPeriod(
        name=kind.value,
        type=kind,
        start_date=start,
        end_date=end,
        faculty_id=faculty.id if faculty else None,
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def two(db: Session) -> tuple[Faculty, Faculty]:
    return make_faculty(db, "Drept"), make_faculty(db, "Inginerie")


# --- the lookup -----------------------------------------------------------------------


def test_a_faculty_period_applies_to_that_faculty_only(db: Session, two) -> None:
    law, engineering = two
    period(db, E, MONDAY, MONDAY, law)

    assert get_period_type_for_date(db, MONDAY, law.id) == E
    assert get_period_type_for_date(db, MONDAY, engineering.id) == T
    assert get_period_type_for_date(db, MONDAY) == T


def test_a_faculty_without_its_own_period_follows_the_all_faculties_one(db: Session, two) -> None:
    law, _ = two
    period(db, H, MONDAY, MONDAY)

    assert get_period_type_for_date(db, MONDAY, law.id) == H
    assert get_period_type_for_date(db, MONDAY) == H


def test_a_faculty_period_wins_over_the_all_faculties_one(db: Session, two) -> None:
    law, engineering = two
    period(db, H, MONDAY, MONDAY)
    period(db, T, MONDAY, MONDAY, law)

    assert get_period_type_for_date(db, MONDAY, law.id) == T
    assert get_period_type_for_date(db, MONDAY, engineering.id) == H


def test_periods_overlap_only_within_the_same_scope(db: Session, two) -> None:
    law, engineering = two
    mine = period(db, E, MONDAY, MONDAY, law)

    assert find_overlapping_period(db, MONDAY, MONDAY, faculty_id=law.id) == mine
    assert find_overlapping_period(db, MONDAY, MONDAY, faculty_id=engineering.id) is None
    assert find_overlapping_period(db, MONDAY, MONDAY) is None


# --- weekly courses and bookings ------------------------------------------------------


def make_unit(db: Session, faculty: Faculty) -> PlanningTimeUnit:
    row = PlanningTimeUnit(
        faculty_id=faculty.id,
        external_id=1,
        year=2031,
        name="Semestrul 1",
        type=PlanningUnitType.SEMESTER,
        start_date=date(2031, 10, 6),
        end_date=date(2032, 1, 31),
    )
    db.add(row)
    db.flush()
    return row


def make_room(db: Session, faculty: Faculty | None) -> Classroom:
    tag = uuid.uuid4().hex[:8]
    row = Classroom(
        name=f"F-{tag}",
        capacity=30,
        external_id=f"f-{tag}",
        faculty_id=faculty.id if faculty else None,
    )
    db.add(row)
    db.flush()
    return row


def weekly(db: Session, unit: PlanningTimeUnit, room: Classroom, name: str, hour: int) -> None:
    db.add(
        Activity(
            name=name,
            type=ActivityType.COURSE,
            priority=Priority.COURSE,
            classroom_id=room.id,
            day_of_week=1,
            start_time=time(hour, 0),
            end_time=time(hour + 1, 0),
            parity=Parity.ALL,
            planning_time_unit_id=unit.id,
            external_id=f"{name}-{uuid.uuid4().hex[:8]}",
        )
    )
    db.flush()


def test_a_session_hides_only_that_faculty_s_courses_even_in_a_shared_room(
    db: Session, two
) -> None:
    law, engineering = two
    room = make_room(db, law)
    weekly(db, make_unit(db, law), room, "Drept civil", 8)
    weekly(db, make_unit(db, engineering), room, "Mecanica", 10)
    period(db, E, MONDAY, MONDAY, law)

    found = occurrences(db, MONDAY, MONDAY, Activity.classroom_id == room.id)

    assert [o.activity.name for o in found] == ["Mecanica"]


NOW = datetime(2031, 11, 24, 12, 0, tzinfo=LOCAL_TZ)


@pytest.fixture
def student(db: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.routers.bookings.local_now", lambda: NOW)
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-fac-s", "fac.s@ulbsibiu.ro")
    return client


def book(client, room: Classroom, start: str, end: str):
    return client.post(
        "/api/bookings",
        json={
            "classroom_id": str(room.id),
            "specific_date": MONDAY.isoformat(),
            "start_time": start,
            "end_time": end,
            "title": "Study",
        },
    )


def test_a_booking_follows_the_room_s_faculty(db: Session, two, student) -> None:
    law, engineering = two
    law_room, engineering_room = make_room(db, law), make_room(db, engineering)
    period(db, E, MONDAY, MONDAY, law)

    assert book(student, law_room, "10:00", "11:00").status_code == 201
    assert book(student, engineering_room, "10:00", "11:00").status_code == 400
    assert book(student, engineering_room, "09:40", "11:10").status_code == 201


def test_a_campus_room_follows_the_all_faculties_periods(db: Session, two, student) -> None:
    law, _ = two
    campus = make_room(db, None)
    period(db, H, MONDAY, MONDAY, law)

    assert book(student, campus, "09:40", "11:10").status_code == 201

    period(db, H, MONDAY, MONDAY)
    assert book(student, campus, "13:00", "14:30").status_code == 400


# --- the admin API --------------------------------------------------------------------


def test_an_admin_sets_a_period_for_a_faculty_or_for_all(db: Session, two, admin) -> None:  # noqa: F811
    law, engineering = two
    dates = {"start": "2033-02-01", "end": "2033-02-10"}

    everyone = admin.post(URL, json=body("Toate", "HOLIDAY", **dates))
    assert everyone.status_code == 201
    assert everyone.json()["faculty_id"] is None
    assert everyone.json()["faculty_name"] is None

    mine = admin.post(URL, json={**body("Drept", **dates), "faculty_id": str(law.id)})
    assert mine.status_code == 201
    assert mine.json()["faculty_id"] == str(law.id)
    assert mine.json()["faculty_name"] == "Drept"

    other = {**body("Ing", **dates), "faculty_id": str(engineering.id)}
    assert admin.post(URL, json=other).status_code == 201
    again = {**body("Din nou", **dates), "faculty_id": str(law.id)}
    assert admin.post(URL, json=again).status_code == 409

    listed = admin.get("/api/academic-periods").json()
    assert mine.json() in listed


def test_an_update_can_move_a_period_to_another_faculty(db: Session, two, admin) -> None:  # noqa: F811
    law, engineering = two
    dates = {"start": "2033-03-01", "end": "2033-03-10"}
    first = admin.post(URL, json={**body("A", **dates), "faculty_id": str(law.id)}).json()
    admin.post(URL, json={**body("B", **dates), "faculty_id": str(engineering.id)})

    url = f"{URL}/{first['id']}"
    taken = admin.put(url, json={**body("A", **dates), "faculty_id": str(engineering.id)})
    assert taken.status_code == 409

    to_all = admin.put(url, json=body("A", **dates))
    assert to_all.status_code == 200
    assert to_all.json()["faculty_id"] is None


def test_an_unknown_faculty_is_a_404(admin) -> None:  # noqa: F811
    unknown = {**body(), "faculty_id": str(uuid.uuid4())}
    assert admin.post(URL, json=unknown).status_code == 404


# --- the professor's faculties --------------------------------------------------------


def test_the_professor_s_faculties_are_listed_even_when_courses_are_hidden(
    db: Session,
    world,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.routers.professors.local_today", lambda: date(2026, 11, 20))
    db.add(
        AcademicPeriod(
            name="Sesiune",
            type=E,
            start_date=date(2026, 11, 16),
            end_date=date(2026, 11, 22),
        )
    )
    db.flush()
    client = make_client(db)
    sign_in_as(db, client, monkeypatch, "sub-fac-p", world["email"], Role.PROFESSOR)

    got = client.get("/api/professors/me/timetable", params={"week_start": "2026-11-16"}).json()

    assert [f["name"] for f in got["faculties"]] == ["Facultatea de Test"]
    assert got["faculties"][0]["id"] == str(world["room"].faculty_id)
