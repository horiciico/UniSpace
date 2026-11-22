"""The free-room search, the timetable and the lookups (GET /api/classrooms/free, /api/schedule,
/api/faculties, /api/groups, /api/professors, /api/classrooms).

DB tests: the endpoints run against the rolled-back `db` fixture (PATTERN-005, PATTERN-006).
Week numbers: the planning unit below starts on Monday 2026-10-05, so
  2026-11-16 is week 7 (ODD), 2026-11-23 is week 8 (EVEN).
"""
import uuid
from collections.abc import Iterator
from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import app
from app.models import (
    Activity,
    ActivityGroup,
    ActivityType,
    Classroom,
    Faculty,
    Parity,
    PlanningTimeUnit,
    PlanningUnitType,
    Priority,
    StudentGroup,
)
from app.planning import parity_for_week, week_monday, week_number

MONDAY_ODD_WEEK = "2026-11-16"  # week 7
MONDAY_EVEN_WEEK = "2026-11-23"  # week 8


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def world(db: Session) -> dict:
    """One faculty with a planning unit, two rooms (one owned, one campus), one bookable-off room."""
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

    owned = Classroom(name=f"A-{tag}", capacity=30, has_projector=True, is_field_verified=True,
                      faculty_id=faculty.id, external_id=f"own-{tag}")
    campus = Classroom(name=f"B-{tag}", capacity=10, faculty_id=None, external_id=f"cam-{tag}")
    closed = Classroom(name=f"C-{tag}", capacity=50, is_bookable=False, faculty_id=faculty.id,
                       external_id=f"off-{tag}")
    db.add_all([owned, campus, closed])
    db.flush()

    group = StudentGroup(name=f"G-{tag}", external_id=int(tag, 16) % 2_000_000_000)
    db.add(group)
    db.flush()

    professor = f"Prof {tag}"
    course = Activity(
        name="Algebra", type=ActivityType.COURSE, priority=Priority.COURSE, classroom_id=owned.id,
        day_of_week=1, start_time=time(10, 0), end_time=time(12, 0), parity=Parity.ODD,
        planning_time_unit_id=unit.id, external_id=f"c-{tag}", professor_name=professor,
    )
    seminar = Activity(
        name="Seminar X", type=ActivityType.SEMINAR, priority=Priority.COURSE, classroom_id=owned.id,
        day_of_week=1, start_time=time(13, 0), end_time=time(14, 0), parity=Parity.ALL,
        planning_time_unit_id=unit.id, external_id=f"s-{tag}",
        professor_name=f"{professor} / Alt {tag}",
    )
    one_off = Activity(
        name="Colocviu", type=ActivityType.EXAM, priority=Priority.EXAM, classroom_id=owned.id,
        day_of_week=1, start_time=time(15, 0), end_time=time(16, 0), parity=Parity.ALL,
        specific_date=date(2026, 11, 23),
    )
    db.add_all([course, seminar, one_off])
    db.flush()
    db.add(ActivityGroup(activity_id=course.id, group_id=group.id))
    db.flush()
    return {
        "faculty": faculty, "unit": unit, "owned": owned, "campus": campus, "closed": closed,
        "group": group, "professor": professor, "course": course, "seminar": seminar,
        "one_off": one_off, "tag": tag,
    }


def free_ids(response_json: list[dict], world: dict) -> dict[str, dict]:
    """The rows of this test's rooms in a free-room response, by room id."""
    ours = {str(world[key].id) for key in ("owned", "campus", "closed")}
    return {row["id"]: row for row in response_json if row["id"] in ours}


# --- week rules -------------------------------------------------------------------------

def test_week_one_is_the_week_of_the_unit_start() -> None:
    start = date(2026, 10, 5)  # a Monday
    assert week_number(start, date(2026, 10, 7)) == 1
    assert week_number(start, date(2026, 10, 12)) == 2
    assert week_number(start, date(2026, 11, 16)) == 7
    assert parity_for_week(7) is Parity.ODD and parity_for_week(8) is Parity.EVEN
    assert week_monday(date(2026, 11, 22)) == date(2026, 11, 16)  # a Sunday belongs to the week before


# --- /api/classrooms/free ---------------------------------------------------------------

def test_free_at_a_moment_is_blocked_by_a_running_course(client: TestClient, world: dict) -> None:
    response = client.get("/api/classrooms/free", params={
        "date": MONDAY_ODD_WEEK, "start_time": "10:30", "faculty_id": str(world["faculty"].id),
    })
    assert response.status_code == 200
    assert response.json() == []  # the only room of the faculty is in use at 10:30 (course, odd week)


def test_course_does_not_run_in_an_even_week(client: TestClient, world: dict) -> None:
    response = client.get("/api/classrooms/free", params={
        "date": MONDAY_EVEN_WEEK, "start_time": "10:30", "faculty_id": str(world["faculty"].id),
    })
    rooms = response.json()
    assert len(rooms) == 1
    assert rooms[0]["id"] == str(world["owned"].id)
    assert rooms[0]["free_until"] == "13:00"  # next: the seminar; the one-off is at 15:00


def test_free_until_is_null_when_nothing_follows(client: TestClient, world: dict) -> None:
    response = client.get("/api/classrooms/free", params={"date": MONDAY_ODD_WEEK, "start_time": "17:00"})
    rows = free_ids(response.json(), world)
    assert rows[str(world["campus"].id)]["free_until"] is None
    assert str(world["closed"].id) not in rows  # not bookable


def test_interval_overlapping_a_seminar_is_taken(client: TestClient, world: dict) -> None:
    response = client.get("/api/classrooms/free", params={
        "date": MONDAY_ODD_WEEK, "start_time": "12:00", "end_time": "13:30",
        "faculty_id": str(world["faculty"].id),
    })
    assert response.json() == []


def test_interval_that_ends_before_a_seminar_is_free(client: TestClient, world: dict) -> None:
    response = client.get("/api/classrooms/free", params={
        "date": MONDAY_ODD_WEEK, "start_time": "12:00", "end_time": "12:45",
        "faculty_id": str(world["faculty"].id),
    })
    assert [row["id"] for row in response.json()] == [str(world["owned"].id)]


def test_campus_filter_and_capacity(client: TestClient, world: dict) -> None:
    campus = client.get("/api/classrooms/free", params={
        "date": MONDAY_ODD_WEEK, "start_time": "17:00", "faculty_id": "campus",
    }).json()
    assert str(world["campus"].id) in {row["id"] for row in campus}
    assert str(world["owned"].id) not in {row["id"] for row in campus}

    big = client.get("/api/classrooms/free", params={
        "date": MONDAY_ODD_WEEK, "start_time": "17:00", "min_capacity": 20,
        "faculty_id": str(world["faculty"].id),
    }).json()
    assert [row["id"] for row in big] == [str(world["owned"].id)]


def test_projector_and_verified_filters(client: TestClient, world: dict) -> None:
    params = {"date": MONDAY_ODD_WEEK, "start_time": "17:00", "faculty_id": str(world["faculty"].id)}
    assert [r["id"] for r in client.get("/api/classrooms/free", params={**params, "has_projector": "true"}).json()] \
        == [str(world["owned"].id)]
    assert client.get("/api/classrooms/free", params={**params, "only_verified": "true"}).json()[0]["is_field_verified"]
    assert client.get("/api/classrooms/free", params={**params, "only_verified": "true", "has_projector": "true"}).json()


def test_verified_rooms_sort_first(client: TestClient, world: dict) -> None:
    response = client.get("/api/classrooms/free", params={"date": MONDAY_ODD_WEEK, "start_time": "17:00"})
    rows = free_ids(response.json(), world)
    ordered = [row["id"] for row in response.json() if row["id"] in rows]
    assert ordered.index(str(world["owned"].id)) < ordered.index(str(world["campus"].id))


def test_end_time_must_follow_start(client: TestClient) -> None:
    response = client.get("/api/classrooms/free", params={"start_time": "12:00", "end_time": "11:00"})
    assert response.status_code == 400


def test_bad_faculty_id_is_400(client: TestClient) -> None:
    assert client.get("/api/classrooms/free", params={"faculty_id": "not-a-uuid"}).status_code == 400


# --- /api/schedule ----------------------------------------------------------------------

def test_schedule_needs_exactly_one_entity(client: TestClient, world: dict) -> None:
    assert client.get("/api/schedule").status_code == 400
    both = client.get("/api/schedule", params={
        "group_id": str(world["group"].id), "room_id": str(world["owned"].id),
    })
    assert both.status_code == 400


def test_group_timetable_respects_parity(client: TestClient, world: dict) -> None:
    odd = client.get("/api/schedule", params={"group_id": str(world["group"].id), "date": MONDAY_ODD_WEEK}).json()
    assert (odd["week_start"], odd["week_end"]) == ("2026-11-16", "2026-11-22")
    assert (odd["week_number"], odd["parity"]) == (7, "ODD")
    assert [item["title"] for item in odd["items"]] == ["Algebra"]
    assert odd["items"][0]["groups"] == [world["group"].name]
    assert odd["items"][0]["start_time"] == "10:00"

    even = client.get("/api/schedule", params={"group_id": str(world["group"].id), "date": MONDAY_EVEN_WEEK}).json()
    assert (even["week_number"], even["parity"]) == (8, "EVEN")
    assert even["items"] == []


def test_room_timetable_has_recurring_and_one_off_items(client: TestClient, world: dict) -> None:
    body = client.get("/api/schedule", params={"room_id": str(world["owned"].id), "date": MONDAY_EVEN_WEEK}).json()
    assert body["entity_type"] == "room" and body["entity_label"] == world["owned"].name
    titles = [(item["title"], item["date"], item["is_recurring"]) for item in body["items"]]
    assert titles == [
        ("Seminar X", "2026-11-23", True),
        ("Colocviu", "2026-11-23", False),
    ]


def test_professor_matches_a_name_inside_a_joint_listing(client: TestClient, world: dict) -> None:
    body = client.get("/api/schedule", params={"professor": world["professor"], "date": MONDAY_ODD_WEEK}).json()
    assert sorted(item["title"] for item in body["items"]) == ["Algebra", "Seminar X"]
    partial = client.get("/api/schedule", params={"professor": world["professor"][:4], "date": MONDAY_ODD_WEEK}).json()
    assert partial["items"] == []  # partial names do not match


def test_unknown_group_and_room_are_404(client: TestClient) -> None:
    missing = str(uuid.uuid4())
    assert client.get("/api/schedule", params={"group_id": missing}).status_code == 404
    assert client.get("/api/schedule", params={"room_id": missing}).status_code == 404


# --- lookups ----------------------------------------------------------------------------

def test_faculties_lookup(client: TestClient, world: dict) -> None:
    rows = client.get("/api/faculties").json()
    assert {"id", "code", "name"} <= set(rows[0])
    assert str(world["faculty"].id) in {row["id"] for row in rows}


def test_groups_and_professors_are_scoped_to_the_faculty(client: TestClient, world: dict) -> None:
    groups = client.get("/api/groups", params={"faculty_id": str(world["faculty"].id)}).json()
    assert [g["id"] for g in groups] == [str(world["group"].id)]
    assert groups[0]["faculty_id"] == str(world["faculty"].id)

    names = [p["name"] for p in client.get("/api/professors", params={"faculty_id": str(world["faculty"].id)}).json()]
    assert world["professor"] in names
    assert f"Alt {world['tag']}" in names  # split out of the joint listing

    other = client.get("/api/groups", params={"faculty_id": str(uuid.uuid4())}).json()
    assert other == []


def test_groups_need_a_faculty(client: TestClient) -> None:
    assert client.get("/api/groups").status_code == 422


def test_classroom_lookup_lists_the_flags(client: TestClient, world: dict) -> None:
    rows = client.get("/api/classrooms", params={"faculty_id": str(world["faculty"].id)}).json()
    by_id = {row["id"]: row for row in rows}
    assert by_id[str(world["owned"].id)]["is_field_verified"] is True
    assert by_id[str(world["owned"].id)]["is_bookable"] is True
    assert str(world["campus"].id) not in by_id
    assert str(world["closed"].id) in by_id and by_id[str(world["closed"].id)]["is_bookable"] is False


# --- one planning unit per timetable ----------------------------------------------------

@pytest.fixture
def other_faculty(db: Session, world: dict) -> dict:
    """Another faculty with its own unit, and an activity of that unit in the owned room (Monday 16:00)."""
    tag = world["tag"]
    faculty = Faculty(code=f"u{tag}", name="Alta facultate")
    db.add(faculty)
    db.flush()
    unit = PlanningTimeUnit(
        faculty_id=faculty.id, external_id=2, year=2026, name="Alt semestru",
        type=PlanningUnitType.SEMESTER, start_date=date(2026, 10, 5), end_date=date(2027, 1, 31),
    )
    db.add(unit)
    db.flush()
    intruder = Activity(
        name="Intrus", type=ActivityType.COURSE, priority=Priority.COURSE, classroom_id=world["owned"].id,
        day_of_week=1, start_time=time(16, 0), end_time=time(17, 0), parity=Parity.ALL,
        planning_time_unit_id=unit.id, external_id=f"i-{tag}",
    )
    db.add(intruder)
    db.flush()
    return {"faculty": faculty, "unit": unit, "intruder": intruder}


def titles(response_json: dict) -> set[str]:
    return {item["title"] for item in response_json["items"]}


def test_room_timetable_shows_only_the_selected_faculty_unit(client: TestClient, world: dict,
                                                             other_faculty: dict) -> None:
    room = str(world["owned"].id)
    mine = client.get("/api/schedule", params={
        "room_id": room, "date": MONDAY_EVEN_WEEK, "faculty_id": str(world["faculty"].id),
    }).json()
    assert titles(mine) == {"Seminar X", "Colocviu"}  # the other faculty's "Intrus" is left out
    assert mine["week_number"] == 8 and mine["parity"] == "EVEN"  # from this faculty's unit

    theirs = client.get("/api/schedule", params={
        "room_id": room, "date": MONDAY_EVEN_WEEK, "faculty_id": str(other_faculty["faculty"].id),
    }).json()
    assert titles(theirs) == {"Intrus", "Colocviu"}  # one-off bookings are shown for any unit


def test_without_a_faculty_the_most_used_unit_is_shown(client: TestClient, world: dict,
                                                       other_faculty: dict) -> None:
    # Odd week: the course of the world's unit runs, so that unit has two activities in this room
    # against one of the other faculty's.
    body = client.get("/api/schedule", params={"room_id": str(world["owned"].id), "date": MONDAY_ODD_WEEK}).json()
    assert "Intrus" not in titles(body)
    assert {"Algebra", "Seminar X"} <= titles(body)


def test_a_faculty_without_a_unit_for_the_week_shows_no_week_number(client: TestClient, world: dict,
                                                                    db: Session) -> None:
    faculty = Faculty(code=f"v{world['tag']}", name="Fara semestru")
    db.add(faculty)
    db.flush()
    db.add(PlanningTimeUnit(
        faculty_id=faculty.id, external_id=3, year=2026, name="Vechi",
        type=PlanningUnitType.MODULE, start_date=date(2026, 1, 5), end_date=date(2026, 2, 27),
    ))
    db.flush()
    body = client.get("/api/schedule", params={
        "room_id": str(world["owned"].id), "date": MONDAY_EVEN_WEEK, "faculty_id": str(faculty.id),
    }).json()
    assert body["week_number"] is None and body["parity"] is None
    assert titles(body) == {"Colocviu"}  # only the one-off booking remains
