"""The admin's data import (D-031, C-012): who may start it, one run at a time, what the run does,
and the clashes it reports. The pipelines themselves are tested in etl/."""

import asyncio
import threading
import uuid
from collections.abc import Iterator
from datetime import date, time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import data_import
from app.auth import get_current_user
from app.db import get_db
from app.main import app
from app.models import (
    Activity,
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
    Role,
    Status,
    StudentGroup,
    User,
)
from etl.professors.extract import ExtractResult
from etl.professors.load import LoadReport as ProfessorsReport
from etl.schedule.download import DownloadResult
from etl.schedule.loader import LoadReport
from etl.schedule.sync import SyncResult

URL = "/api/admin/data-import"
MONDAY = date(2026, 12, 7)


@pytest.fixture(autouse=True)
def clean() -> Iterator[None]:
    data_import.reset()
    yield
    data_import.wait(5)
    data_import.reset()
    app.dependency_overrides.clear()


def client_as(role: Role | None) -> TestClient:
    if role is not None:
        app.dependency_overrides[get_current_user] = lambda: User(
            id=uuid.uuid4(), email="x@ulbsibiu.ro", name="X", role=role
        )
    return TestClient(app, base_url="https://testserver")


# --- The endpoint --------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["get", "post"])
def test_it_needs_a_sign_in(db: Session, method: str) -> None:
    app.dependency_overrides[get_db] = lambda: db

    assert getattr(client_as(None), method)(URL).status_code == 401


@pytest.mark.parametrize("role", [Role.STUDENT, Role.PROFESSOR, Role.STUDENT_ORG])
@pytest.mark.parametrize("method", ["get", "post"])
def test_only_an_admin_may_see_or_start_it(role: Role, method: str, monkeypatch) -> None:
    started = []
    monkeypatch.setattr(data_import, "start", lambda: started.append(1) or True)

    assert getattr(client_as(role), method)(URL).status_code == 403
    assert started == []


def test_before_any_run_the_state_is_idle() -> None:
    answer = client_as(Role.ADMIN).get(URL).json()

    assert answer["status"] == "idle"
    assert answer["result"] is None


def test_a_run_goes_on_in_the_background_and_a_second_one_is_refused(monkeypatch) -> None:
    release = threading.Event()

    async def slow(folder: Path, step) -> dict:
        step("schedules")
        while not release.is_set():
            await asyncio.sleep(0.01)
        return {"clashes": []}

    monkeypatch.setattr(data_import, "run_pipeline", slow)
    client = client_as(Role.ADMIN)

    first = client.post(URL)
    second = client.post(URL)

    assert first.status_code == 202
    assert first.json()["status"] == "running"
    assert second.status_code == 409
    assert second.json()["detail"] == "An import is already running."
    release.set()
    data_import.wait(5)
    done = client.get(URL).json()
    assert done["status"] == "done"
    assert done["result"] == {"clashes": []}
    assert done["started_at"] and done["finished_at"]
    assert client.post(URL).status_code == 202


def test_a_failed_run_says_where_without_the_error_text(monkeypatch, caplog) -> None:
    async def broken(folder: Path, step) -> dict:
        step("professors")
        raise RuntimeError("insert failed for someone@ulbsibiu.ro")

    monkeypatch.setattr(data_import, "run_pipeline", broken)
    client = client_as(Role.ADMIN)

    client.post(URL)
    data_import.wait(5)
    answer = client.get(URL)

    assert answer.json()["status"] == "failed"
    assert answer.json()["step"] == "professors"
    assert "someone@" not in answer.text
    assert "someone@" not in caplog.text


# --- The run -------------------------------------------------------------------------------


@pytest.fixture
def pipelines(monkeypatch) -> dict:
    """Stands in for the two pipelines; records what the run asks of them."""
    calls: dict = {"folders": [], "complete": None, "steps": []}

    async def faculties():
        return {"data": []}

    async def sync(*args):
        return [SyncResult("ok1", "ok"), SyncResult("bad1", "error", note="HTTP 500")]

    async def download(code, folder):
        calls["folders"].append(folder)
        return [DownloadResult("ok1", "ok"), DownloadResult("bad2", "error", note="timeout")]

    async def load(code, folder):
        calls["folders"].append(folder)
        return LoadReport(
            inserted=2,
            updated=1,
            unchanged=5,
            restored=1,
            cancelled=3,
            skipped_manual=4,
            unparsed=[("f.json", 1, "S", "reason")],
            empty=["bad3"],
            failed=["bad4"],
        )

    async def extract(codes, folder):
        calls["folders"].append(folder)
        return [ExtractResult("ok1", "ok"), ExtractResult("bad5", "error", note="HTTP 500")]

    def professors(folder, complete):
        calls["folders"].append(folder)
        calls["complete"] = complete
        return ProfessorsReport(stored=7, rekeyed=[("a", "b")])

    monkeypatch.setattr(data_import, "fetch_faculties", faculties)
    monkeypatch.setattr(data_import, "upsert_faculties", lambda db, payload: ["ok1"])
    monkeypatch.setattr(data_import, "sync_planning_units", sync)
    monkeypatch.setattr(data_import, "download_schedules", download)
    monkeypatch.setattr(data_import, "load_all", load)
    monkeypatch.setattr(data_import, "extract_faculties", extract)
    monkeypatch.setattr(data_import, "load_professors", professors)
    monkeypatch.setattr(data_import, "find_clashes", lambda db, first: [{"what": "exam"}])
    return calls


def run(folder: Path, calls: dict) -> dict:
    return asyncio.run(data_import.run_pipeline(folder, calls["steps"].append))


def test_a_run_does_the_schedule_then_the_professors(pipelines: dict, tmp_path: Path) -> None:
    result = run(tmp_path, pipelines)

    assert pipelines["steps"] == [
        "faculties",
        "planning_units",
        "schedules",
        "timetable",
        "professors",
        "clashes",
    ]
    assert result["schedule"] == {
        "inserted": 2,
        "updated": 1,
        "unchanged": 5,
        "restored": 1,
        "cancelled": 3,
        "kept_edited": 4,
        "unread_entries": 1,
    }
    assert result["professors"] == {"stored": 7}
    assert result["problems"] == [
        {"faculty": "bad1", "kind": "planning"},
        {"faculty": "bad2", "kind": "download"},
        {"faculty": "bad3", "kind": "empty"},
        {"faculty": "bad4", "kind": "load"},
        {"faculty": "bad5", "kind": "professors"},
    ]
    assert result["clashes"] == [{"what": "exam"}]


def test_a_run_only_reads_the_files_it_downloaded(pipelines: dict, tmp_path: Path) -> None:
    run(tmp_path, pipelines)

    assert pipelines["folders"] == [
        tmp_path / "schedules",
        tmp_path / "schedules",
        tmp_path / "professors",
        tmp_path / "professors",
    ]


def test_a_missing_professor_file_makes_the_professor_load_partial(
    pipelines: dict, tmp_path: Path
) -> None:
    run(tmp_path, pipelines)

    assert pipelines["complete"] is False


def test_a_professor_save_error_is_a_problem_without_its_text(
    pipelines: dict, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        data_import,
        "load_professors",
        lambda folder, complete: ProfessorsReport(errors=["database error: someone@ulbsibiu.ro"]),
    )

    result = run(tmp_path, pipelines)

    assert {"faculty": None, "kind": "professors_save"} in result["problems"]
    assert "someone@" not in str(result)


# --- The clashes ---------------------------------------------------------------------------


@pytest.fixture
def world(db: Session) -> dict:
    tag = uuid.uuid4().hex[:8]
    faculty = Faculty(code=f"i{tag}", name="Facultatea de Test")
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
    room = Classroom(name=f"R-{tag}", capacity=30, faculty_id=faculty.id, external_id=tag)
    other = Classroom(name=f"S-{tag}", capacity=30, faculty_id=faculty.id, external_id=f"{tag}b")
    group = StudentGroup(name=f"G-{tag}", external_id=int(tag, 16) % 2_000_000_000)
    user = User(email=f"{tag}@ulbsibiu.ro", name="U", role=Role.STUDENT)
    db.add_all([unit, room, other, group, user])
    db.flush()
    professor = uuid.uuid4()

    def activity(name: str, classroom: Classroom, start: time, **kw) -> Activity:
        values = dict(
            name=name,
            type=ActivityType.COURSE,
            priority=Priority.COURSE,
            classroom_id=classroom.id,
            day_of_week=1,
            start_time=start,
            end_time=time(start.hour + 1, 30),
            parity=Parity.ALL,
            status=Status.APPROVED,
        )
        values.update(kw)
        row = Activity(**values)
        db.add(row)
        db.flush()
        return row

    course = activity(
        "Imported",
        room,
        time(8, 0),
        planning_time_unit_id=unit.id,
        external_id=f"c-{tag}",
        professor_id=professor,
    )
    db.add(ActivityGroup(activity_id=course.id, group_id=group.id))

    def booking(day: date, status: BookingStatus = BookingStatus.APPROVED) -> None:
        db.add(
            Booking(
                user_id=user.id,
                classroom_id=room.id,
                specific_date=day,
                start_time=time(9, 0),
                end_time=time(10, 0),
                title="Club",
                status=status,
            )
        )
        db.flush()

    return {
        "room": room,
        "other": other,
        "group": group,
        "professor": professor,
        "activity": activity,
        "booking": booking,
    }


def clashes(db: Session, world: dict) -> list[dict]:
    names = {world["room"].name, world["other"].name}
    return [c for c in data_import.find_clashes(db, MONDAY) if c["room"] in names]


def test_a_booking_over_an_imported_class_is_listed(db: Session, world: dict) -> None:
    world["booking"](MONDAY)

    assert clashes(db, world) == [
        {
            "date": "2026-12-07",
            "start": "09:00",
            "end": "10:00",
            "room": world["room"].name,
            "what": "booking",
            "title": "Club",
            "class_start": "08:00",
            "class_end": "09:30",
            "class_room": world["room"].name,
            "reasons": ["room"],
        }
    ]


def test_past_pending_and_other_day_bookings_are_not_listed(db: Session, world: dict) -> None:
    world["booking"](date(2026, 11, 30))  # before the first day asked for
    world["booking"](MONDAY, BookingStatus.PENDING)
    world["booking"](date(2026, 12, 8))  # a Tuesday: the class is on Mondays

    assert clashes(db, world) == []


def test_an_exam_clashes_by_professor_or_group_in_another_room(db: Session, world: dict) -> None:
    exam = world["activity"](
        "Algebra",
        world["other"],
        time(9, 0),
        type=ActivityType.EXAM,
        specific_date=MONDAY,
        professor_id=world["professor"],
    )
    db.add(ActivityGroup(activity_id=exam.id, group_id=world["group"].id))
    db.flush()

    found = clashes(db, world)

    assert [(c["what"], c["title"], c["reasons"]) for c in found] == [
        ("exam", "Algebra", ["professor", "group"])
    ]
    assert found[0]["class_room"] == world["room"].name


def test_a_moved_class_in_the_same_room_is_listed_and_a_cancelled_one_is_not(
    db: Session, world: dict
) -> None:
    world["activity"]("Moved", world["room"], time(9, 0), specific_date=MONDAY)
    world["activity"](
        "Old", world["room"], time(8, 0), specific_date=MONDAY, status=Status.CANCELLED
    )

    assert [(c["what"], c["title"]) for c in clashes(db, world)] == [("class", "Moved")]


def test_cancelled_classes_leave_the_group_and_professor_lists(db: Session) -> None:
    tag = uuid.uuid4().hex[:8]
    faculty = Faculty(code=f"j{tag}", name="F")
    db.add(faculty)
    db.flush()
    unit = PlanningTimeUnit(
        faculty_id=faculty.id,
        external_id=1,
        year=2026,
        name="S",
        type=PlanningUnitType.SEMESTER,
        start_date=date(2026, 10, 5),
        end_date=date(2027, 1, 31),
    )
    room = Classroom(name=f"T-{tag}", external_id=tag)
    group = StudentGroup(name=f"H-{tag}", external_id=int(tag, 16) % 2_000_000_000)
    db.add_all([unit, room, group])
    db.flush()
    row = Activity(
        name="Gone",
        type=ActivityType.COURSE,
        priority=Priority.COURSE,
        classroom_id=room.id,
        day_of_week=1,
        start_time=time(8, 0),
        end_time=time(9, 30),
        parity=Parity.ALL,
        planning_time_unit_id=unit.id,
        external_id=f"g-{tag}",
        professor_name=f"Prof {tag}",
        status=Status.CANCELLED,
    )
    db.add(row)
    db.flush()
    db.add(ActivityGroup(activity_id=row.id, group_id=group.id))
    db.flush()
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    assert client.get(f"/api/groups?faculty_id={faculty.id}").json() == []
    assert client.get(f"/api/professors?faculty_id={faculty.id}").json() == []
