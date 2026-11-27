"""A professor's subjects and groups, and scheduling an exam (step 1 and step 2 of the exam flow).

- GET /api/professors/me/subjects: the distinct subjects the professor teaches (activities not
  cancelled), each with the groups taking part. Unlinked: linked false and no subjects.
- POST /api/professors/me/exams: one one-off EXAM activity for every selected group, hard-blocked
  (409) when the room, the professor or any group is busy. Whole modules, bookable room,
  no past date.

Today is fixed at 2026-11-20. The exam day is Tuesday 2026-12-08, in an exam session of the
faculty, so its weekly courses are not held then: a busy slot on that day is a one-off.
"""

import uuid
from collections.abc import Iterator
from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import oauth
from app.db import get_db
from app.main import app
from app.models import (
    AcademicPeriod,
    AcademicPeriodType,
    Activity,
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
EXAM_DAY = "2026-12-08"
M0 = ("08:00", "09:30")
M1 = ("09:40", "11:10")


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
    claims = {"sub": sub, "email": email, "email_verified": True, "hd": "ulbsibiu.ro", "name": "T"}

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
    faculty = Faculty(code=f"x{tag}", name="Facultatea de Test")
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

    groups = {
        label: StudentGroup(name=f"{label}-{tag}", external_id=(int(tag, 16) + i) % 2_000_000_000)
        for i, label in enumerate(["3A", "3B", "3C"])
    }
    db.add_all(groups.values())
    db.flush()

    ulbs_id = uuid.uuid4()
    email = f"prof.{tag}@ulbsibiu.ro"
    db.add(Professor(id=ulbs_id, name=f"Prof {tag}", email=email))
    db.flush()

    session = AcademicPeriod(
        name="Sesiune",
        type=AcademicPeriodType.EXAM_SESSION,
        start_date=date(2026, 12, 7),
        end_date=date(2026, 12, 20),
        faculty_id=faculty.id,
    )
    db.add(session)
    db.flush()

    def busy(
        name: str,
        *,
        professor: uuid.UUID | None = None,
        room: Classroom | None = None,
        groups_of: tuple[StudentGroup, ...] = (),
    ) -> None:
        activity = Activity(
            name=name,
            type=ActivityType.EXAM,
            priority=Priority.EXAM,
            classroom_id=(room or room_a).id,
            day_of_week=2,
            start_time=time(8, 0),
            end_time=time(9, 30),
            parity=Parity.ALL,
            specific_date=date(2026, 12, 8),
            professor_id=professor or uuid.uuid4(),
            status=Status.APPROVED,
        )
        db.add(activity)
        db.flush()
        for group in groups_of:
            db.add(ActivityGroup(activity_id=activity.id, group_id=group.id))
        db.flush()

    def weekly(
        name: str,
        span: tuple[time, time],
        *,
        day: int = 1,
        professor: uuid.UUID | None = None,
        room: Classroom | None = None,
        groups_of: tuple[StudentGroup, ...] = (),
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
        for group in groups_of:
            db.add(ActivityGroup(activity_id=activity.id, group_id=group.id))
        db.flush()
        return activity

    os_course = weekly(
        "Sisteme de Operare", (time(8, 0), time(9, 30)), groups_of=(groups["3A"], groups["3B"])
    )
    weekly("Sisteme de Operare", (time(13, 0), time(14, 30)), day=3, groups_of=(groups["3B"],))
    weekly("Retele", (time(9, 40), time(11, 10)), day=4, groups_of=(groups["3C"],))
    weekly(
        "Dropped", (time(11, 20), time(12, 50)), groups_of=(groups["3C"],), status=Status.CANCELLED
    )
    weekly("Other", (time(11, 20), time(12, 50)), professor=uuid.uuid4(), groups_of=(groups["3A"],))
    db.flush()
    return {
        "email": email,
        "ulbs_id": ulbs_id,
        "faculty": faculty,
        "room_a": room_a,
        "room_b": room_b,
        "room_off": room_off,
        "groups": groups,
        "os_course": os_course,
        "weekly": weekly,
        "busy": busy,
        "session": session,
        "tag": tag,
    }


def body(world: dict, **overrides) -> dict:
    data = {
        "subject_name": "Sisteme de Operare",
        "group_ids": [str(world["groups"]["3A"].id), str(world["groups"]["3B"].id)],
        "exam_date": EXAM_DAY,
        "start_time": M0[0],
        "end_time": M0[1],
        "classroom_id": str(world["room_b"].id),
    }
    data.update(overrides)
    return data


def exams_named(db: Session, name: str) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Activity)
        .where(Activity.name == name, Activity.type == ActivityType.EXAM)
    )


@pytest.fixture
def client_signed_in(db, world, monkeypatch) -> TestClient:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-1", world["email"], Role.PROFESSOR)
    return client


# --- subjects ----------------------------------------------------------------------------------


def test_subjects_are_the_distinct_courses_with_their_groups(db, world, client_signed_in) -> None:
    body_ = client_signed_in.get("/api/professors/me/subjects").json()

    assert body_["linked"] is True
    assert [s["name"] for s in body_["subjects"]] == ["Retele", "Sisteme de Operare"]
    operating = next(s for s in body_["subjects"] if s["name"] == "Sisteme de Operare")
    assert operating["groups"] == [
        {"id": str(world["groups"]["3A"].id), "name": world["groups"]["3A"].name},
        {"id": str(world["groups"]["3B"].id), "name": world["groups"]["3B"].name},
    ]


def test_a_cancelled_or_other_professors_subject_is_not_listed(db, world, client_signed_in) -> None:
    names = [
        s["name"] for s in client_signed_in.get("/api/professors/me/subjects").json()["subjects"]
    ]

    assert "Dropped" not in names
    assert "Other" not in names


def test_a_subject_with_no_group_lists_no_groups(db, world, client_signed_in) -> None:
    world["weekly"]("Seminar fara grupa", (time(13, 0), time(14, 30)), day=5)

    subjects = client_signed_in.get("/api/professors/me/subjects").json()["subjects"]

    assert {"name": "Seminar fara grupa", "groups": []} in subjects


def test_an_unlinked_professor_has_no_subjects(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-2", "nobody.linked@ulbsibiu.ro", Role.PROFESSOR)

    assert client.get("/api/professors/me/subjects").json() == {"linked": False, "subjects": []}


def test_subjects_are_for_professors_only_and_need_a_sign_in(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-3", world["email"], Role.STUDENT)

    assert client.get("/api/professors/me/subjects").status_code == 403
    assert make_client(db).get("/api/professors/me/subjects").status_code == 401


# --- scheduling an exam ------------------------------------------------------------------------


def test_an_exam_is_one_approved_one_off_for_every_group(db, world, client_signed_in) -> None:
    response = client_signed_in.post("/api/professors/me/exams", json=body(world))

    assert response.status_code == 201, response.text
    data = response.json()
    exam = db.get(Activity, uuid.UUID(data["id"]))
    assert exam.name == "Sisteme de Operare"
    assert exam.type == ActivityType.EXAM
    assert exam.priority == Priority.EXAM
    assert exam.specific_date == date(2026, 12, 8)
    assert exam.day_of_week == 2
    assert exam.start_time == time(8, 0)
    assert exam.end_time == time(9, 30)
    assert exam.classroom_id == world["room_b"].id
    assert exam.status == Status.APPROVED
    assert exam.is_manually_modified is True
    assert exam.professor_id == world["ulbs_id"]
    assert exam.professor_name == f"Prof {world['tag']}"
    assert exam.user_id is not None
    groups = set(
        db.scalars(select(ActivityGroup.group_id).where(ActivityGroup.activity_id == exam.id)).all()
    )
    assert groups == {world["groups"]["3A"].id, world["groups"]["3B"].id}
    assert data["groups"] == sorted([world["groups"]["3A"].name, world["groups"]["3B"].name])


def test_the_exam_shows_in_the_group_timetable(db, world, client_signed_in) -> None:
    client_signed_in.post("/api/professors/me/exams", json=body(world))

    shown = (
        make_client(db)
        .get("/api/schedule", params={"group_id": str(world["groups"]["3A"].id), "date": EXAM_DAY})
        .json()
    )

    assert any(i["title"] == "Sisteme de Operare" and i["date"] == EXAM_DAY for i in shown["items"])


@pytest.mark.parametrize(
    "overrides",
    [
        {"subject_name": "Not taught"},
        {"group_ids": []},
        {"exam_date": "2026-11-19"},
        # The 30-minute grid, D-030: start on :00 or :30, length a multiple of 30 min, at least 1 h.
        {"start_time": "08:15", "end_time": "09:45"},
        {"start_time": "08:00", "end_time": "08:45"},
        {"start_time": "08:00", "end_time": "08:30"},
        {"start_time": "07:30", "end_time": "09:30"},
        {"start_time": "20:30", "end_time": "21:40"},
        {"start_time": "21:00", "end_time": "22:30"},
        {"start_time": "10:00", "end_time": "09:00"},
    ],
)
def test_bad_input_is_400_and_saves_nothing(db, world, client_signed_in, overrides) -> None:
    response = client_signed_in.post("/api/professors/me/exams", json=body(world, **overrides))

    assert response.status_code == 400, response.text
    assert exams_named(db, "Sisteme de Operare") == 0


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("08:00", "11:00"),
        ("08:30", "10:00"),
        ("14:30", "19:30"),
        ("08:00", "09:30"),
        ("18:00", "21:30"),
        ("20:00", "22:00"),
    ],
)
def test_any_half_hour_start_and_length_of_an_hour_or_more_is_accepted(
    db, world, client_signed_in, start, end
) -> None:
    response = client_signed_in.post(
        "/api/professors/me/exams",
        json=body(world, start_time=start, end_time=end, group_ids=[str(world["groups"]["3A"].id)]),
    )

    assert response.status_code == 201, response.text
    assert response.json()["start_time"] == start
    assert response.json()["end_time"] == end


def test_a_group_not_taught_in_the_subject_is_400(db, world, client_signed_in) -> None:
    other_group = str(world["groups"]["3C"].id)

    response = client_signed_in.post(
        "/api/professors/me/exams", json=body(world, group_ids=[other_group])
    )

    assert response.status_code == 400
    assert exams_named(db, "Sisteme de Operare") == 0


def test_an_unknown_room_is_404_and_an_unbookable_one_400(db, world, client_signed_in) -> None:
    unknown = client_signed_in.post(
        "/api/professors/me/exams", json=body(world, classroom_id=str(uuid.uuid4()))
    )
    closed = client_signed_in.post(
        "/api/professors/me/exams", json=body(world, classroom_id=str(world["room_off"].id))
    )

    assert unknown.status_code == 404
    assert closed.status_code == 400


def test_a_busy_room_is_409(db, world, client_signed_in) -> None:
    world["busy"]("Other class", room=world["room_b"])

    response = client_signed_in.post("/api/professors/me/exams", json=body(world))

    assert response.status_code == 409
    assert "Room busy" in response.json()["detail"]
    assert exams_named(db, "Sisteme de Operare") == 0


def test_a_busy_professor_is_409(db, world, client_signed_in) -> None:
    world["busy"]("Own class", professor=world["ulbs_id"], room=world["room_b"])

    response = client_signed_in.post("/api/professors/me/exams", json=body(world))

    assert response.status_code == 409
    assert "Professor busy" in response.json()["detail"]


def test_any_busy_group_is_409_and_names_it(db, world, client_signed_in) -> None:
    world["busy"]("Lab 3B", room=world["room_a"], groups_of=(world["groups"]["3B"],))

    response = client_signed_in.post("/api/professors/me/exams", json=body(world))

    assert response.status_code == 409
    assert world["groups"]["3B"].name in response.json()["detail"]
    assert world["groups"]["3A"].name not in response.json()["detail"]


def test_a_student_and_an_unlinked_professor_are_403(db, world, monkeypatch) -> None:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-4", world["email"], Role.STUDENT)
    assert client.post("/api/professors/me/exams", json=body(world)).status_code == 403

    other = make_client(db)
    sign_in(db, other, monkeypatch, "sub-5", "nobody.linked@ulbsibiu.ro", Role.PROFESSOR)
    assert other.post("/api/professors/me/exams", json=body(world)).status_code == 403


def test_it_needs_a_sign_in(db, world) -> None:
    assert make_client(db).post("/api/professors/me/exams", json=body(world)).status_code == 401



# --- the exam session, per faculty (D-030) -----------------------------------------------------

NO_SESSION = "The date is not in an exam session for these groups."


def schedule(client, world: dict, **overrides):
    return client.post("/api/professors/me/exams", json=body(world, **overrides))


def other_faculty(db) -> Faculty:
    row = Faculty(code=f"o{uuid.uuid4().hex[:8]}", name="Alta facultate")
    db.add(row)
    db.flush()
    return row


def set_period(db, kind, faculty: Faculty | None, day: date) -> None:
    db.add(
        AcademicPeriod(
            name=kind.value,
            type=kind,
            start_date=day,
            end_date=day,
            faculty_id=faculty.id if faculty else None,
        )
    )
    db.flush()


def test_a_date_outside_the_exam_session_is_400(db, world, client_signed_in) -> None:
    response = schedule(client_signed_in, world, exam_date="2026-12-01")

    assert response.status_code == 400
    assert response.json()["detail"] == NO_SESSION
    assert exams_named(db, "Sisteme de Operare") == 0


def test_another_faculty_s_session_does_not_count(db, world, client_signed_in) -> None:
    set_period(db, AcademicPeriodType.EXAM_SESSION, other_faculty(db), date(2026, 12, 1))

    assert schedule(client_signed_in, world, exam_date="2026-12-01").status_code == 400


def test_a_session_for_all_faculties_counts(db, world, client_signed_in) -> None:
    set_period(db, AcademicPeriodType.EXAM_SESSION, None, date(2026, 12, 1))

    response = schedule(client_signed_in, world, exam_date="2026-12-01")

    assert response.status_code == 201, response.text


def test_the_room_s_faculty_need_not_be_in_a_session(db, world, client_signed_in) -> None:
    world["room_b"].faculty_id = other_faculty(db).id
    db.flush()

    assert schedule(client_signed_in, world).status_code == 201


def test_a_room_whose_faculty_is_on_holiday_is_refused(db, world, client_signed_in) -> None:
    faculty = other_faculty(db)
    world["room_b"].faculty_id = faculty.id
    set_period(db, AcademicPeriodType.HOLIDAY, faculty, date(2026, 12, 8))

    response = schedule(client_signed_in, world)

    assert response.status_code == 400
    assert response.json()["detail"] == "The room is closed for a holiday on that date."


def interval(client, world: dict, day: str = EXAM_DAY) -> dict:
    response = client.get(
        "/api/professors/me/availability/interval",
        params={
            "date": day,
            "start_time": "10:00",
            "end_time": "12:00",
            "group_ids": str(world["groups"]["3A"].id),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_the_interval_says_whether_the_groups_are_in_a_session(
    db, world, client_signed_in
) -> None:
    assert interval(client_signed_in, world)["exam_session"] is True
    assert interval(client_signed_in, world, "2026-12-01")["exam_session"] is False


def test_the_interval_leaves_out_rooms_on_holiday(db, world, client_signed_in) -> None:
    faculty = other_faculty(db)
    world["room_b"].faculty_id = faculty.id
    set_period(db, AcademicPeriodType.HOLIDAY, faculty, date(2026, 12, 8))

    free = {r["id"] for r in interval(client_signed_in, world)["free_classrooms"]}

    assert str(world["room_b"].id) not in free
    assert str(world["room_a"].id) in free
