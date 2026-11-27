"""The calendar is checked when a class is moved and when a booking is approved (D-029), and the
period endpoints are safe against bad times, concurrent saves and the last possible date.

DB tests: they need PostgreSQL (compose `db`); see conftest.py.
"""

from datetime import date, time

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import (
    AcademicPeriod,
    AcademicPeriodType,
    Booking,
    BookingStatus,
    Classroom,
    Faculty,
)
from app.planning import occurrences
from app.routers.academic_periods import PERIODS_LOCK, PeriodBody, check_body
from tests.test_academic_calendar_faculty import make_faculty, make_room, period
from tests.test_admin_bookings import booking
from tests.test_admin_bookings import make_client as admin_client
from tests.test_admin_bookings import sign_in as admin_sign_in
from tests.test_bookings_api import make_client as booking_client
from tests.test_bookings_api import reset_overrides, sign_in  # noqa: F401
from tests.test_professor_move import (
    client_signed_in,  # noqa: F401
    exceptions_of,
    fixed_today,  # noqa: F401
    move,
    move_body,
    world,  # noqa: F401
)

H, E, T = (
    AcademicPeriodType.HOLIDAY,
    AcademicPeriodType.EXAM_SESSION,
    AcademicPeriodType.TEACHING,
)
TUE = date(2026, 11, 24)  # the new date of move_body
HOLIDAY_DETAIL = "The new date is a holiday. A class cannot be moved to it."


def teaching_faculty(db: Session, world: dict) -> Faculty:  # noqa: F811
    return db.get(Faculty, world["room_a"].faculty_id)


# --- moving a class -------------------------------------------------------------------


def test_a_class_cannot_move_to_a_holiday_for_all_faculties(
    db,
    world,  # noqa: F811
    client_signed_in,  # noqa: F811
) -> None:
    period(db, H, TUE, TUE)

    response = move(client_signed_in, world["algebra"], move_body(world["room_b"]))

    assert response.status_code == 400
    assert response.json()["detail"] == HOLIDAY_DETAIL
    assert exceptions_of(db, world["algebra"]) == []


def test_a_holiday_of_the_teaching_faculty_blocks_a_move_to_another_faculty_s_room(
    db,
    world,  # noqa: F811
    client_signed_in,  # noqa: F811
) -> None:
    other = make_faculty(db, "Alta")
    room = make_room(db, other)
    room.is_bookable = True
    period(db, H, TUE, TUE, teaching_faculty(db, world))

    response = move(client_signed_in, world["algebra"], move_body(room))

    assert response.status_code == 400


def test_a_holiday_of_the_room_s_faculty_blocks_the_move(
    db,
    world,  # noqa: F811
    client_signed_in,  # noqa: F811
) -> None:
    other = make_faculty(db, "Alta")
    room = make_room(db, other)
    room.is_bookable = True
    period(db, H, TUE, TUE, other)

    response = move(client_signed_in, world["algebra"], move_body(room))

    assert response.status_code == 400


def test_another_faculty_s_holiday_does_not_block_a_move(
    db,
    world,  # noqa: F811
    client_signed_in,  # noqa: F811
) -> None:
    period(db, H, TUE, TUE, make_faculty(db, "Alta"))

    response = move(client_signed_in, world["algebra"], move_body(world["room_b"]))

    assert response.status_code == 200, response.text


def test_an_already_moved_class_still_follows_its_faculty_s_holidays(
    db,
    world,  # noqa: F811
    client_signed_in,  # noqa: F811
) -> None:
    # The one-off a move creates has no planning unit; its group still tells the faculty.
    other = make_faculty(db, "Alta")
    room = make_room(db, other)
    room.is_bookable = True
    moved = move(client_signed_in, world["algebra"], move_body(world["room_b"]))
    assert moved.status_code == 200, moved.text
    period(db, H, date(2026, 11, 25), date(2026, 11, 25), teaching_faculty(db, world))

    response = client_signed_in.post(
        f"/api/professors/me/activities/{moved.json()['id']}/move",
        json=move_body(room, original_date="2026-11-24", new_date="2026-11-25"),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == HOLIDAY_DETAIL


def availability(client, activity, **params):
    return client.get(
        "/api/professors/me/availability",
        params={"date": TUE.isoformat(), "exclude_activity_id": str(activity.id), **params},
    ).json()["modules"]


def test_the_move_dialog_says_a_holiday_is_why_no_module_is_free(
    db,
    world,  # noqa: F811
    client_signed_in,  # noqa: F811
) -> None:
    period(db, H, TUE, TUE, teaching_faculty(db, world))

    modules = availability(client_signed_in, world["algebra"])

    assert [m["available"] for m in modules] == [False] * 8
    assert {m["conflict_reason"] for m in modules} == {"Holiday."}


def test_rooms_of_a_faculty_on_holiday_are_not_offered(
    db,
    world,  # noqa: F811
    client_signed_in,  # noqa: F811
) -> None:
    other = make_faculty(db, "Alta")
    room = make_room(db, other)
    room.is_bookable = True
    period(db, H, TUE, TUE, other)

    modules = availability(client_signed_in, world["algebra"])

    offered = {r["id"] for r in modules[0]["free_classrooms"]}
    assert modules[0]["available"] is True
    assert str(room.id) not in offered
    assert str(world["room_b"].id) in offered


# --- no classes in an exam session ----------------------------------------------------

EXAM_DETAIL = "The new date is in an exam session. A class cannot be moved to it."


def test_a_class_cannot_move_into_its_faculty_s_exam_session(
    db,
    world,  # noqa: F811
    client_signed_in,  # noqa: F811
) -> None:
    period(db, E, TUE, TUE, teaching_faculty(db, world))

    response = move(client_signed_in, world["algebra"], move_body(world["room_b"]))

    assert response.status_code == 400
    assert response.json()["detail"] == EXAM_DETAIL
    assert exceptions_of(db, world["algebra"]) == []


def test_a_class_cannot_move_into_a_room_whose_faculty_is_in_an_exam_session(
    db,
    world,  # noqa: F811
    client_signed_in,  # noqa: F811
) -> None:
    other = make_faculty(db, "Alta")
    room = make_room(db, other)
    room.is_bookable = True
    period(db, E, TUE, TUE, other)

    assert move(client_signed_in, world["algebra"], move_body(room)).status_code == 400


def test_another_faculty_s_exam_session_does_not_block_a_move(
    db,
    world,  # noqa: F811
    client_signed_in,  # noqa: F811
) -> None:
    period(db, E, TUE, TUE, make_faculty(db, "Alta"))

    response = move(client_signed_in, world["algebra"], move_body(world["room_b"]))

    assert response.status_code == 200, response.text


def test_the_move_dialog_says_an_exam_session_is_why_no_module_is_free(
    db,
    world,  # noqa: F811
    client_signed_in,  # noqa: F811
) -> None:
    period(db, E, TUE, TUE, teaching_faculty(db, world))

    modules = availability(client_signed_in, world["algebra"])

    assert [m["available"] for m in modules] == [False] * 8
    assert {m["conflict_reason"] for m in modules} == {"Exam session."}


def test_an_exam_itself_can_still_be_moved_within_the_session(
    db,
    world,  # noqa: F811
    client_signed_in,  # noqa: F811
) -> None:
    exam = world["one_off"]("Colocviu", date(2026, 11, 23), (time(8, 0), time(9, 30)))
    period(db, E, date(2026, 11, 23), TUE, teaching_faculty(db, world))

    modules = availability(client_signed_in, exam)
    assert modules[1]["available"] is True

    response = move(client_signed_in, exam, move_body(world["room_b"]))

    assert response.status_code == 200, response.text


# --- approving a pending booking ------------------------------------------------------


def decide(db, monkeypatch, room: Classroom, kind, decision="approve", **times):
    client = admin_client(db)
    user = admin_sign_in(db, client, monkeypatch, "sub-chk", "chk@ulbsibiu.ro")
    admin = admin_client(db)
    from app.models import Role

    admin_sign_in(db, admin, monkeypatch, "sub-chk-a", "chk.a@ulbsibiu.ro", Role.ADMIN)
    row = booking(db, user, room, **times)
    if kind is not None:
        period(db, kind, row.specific_date, row.specific_date)
    response = admin.post(f"/api/admin/bookings/{row.id}/decision", json={"decision": decision})
    return response, db.get(Booking, row.id)


def test_a_booking_cannot_be_approved_once_its_date_is_a_holiday(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    response, row = decide(db, monkeypatch, make_room(db, None), H)

    assert response.status_code == 400
    assert response.json()["detail"] == "Bookings are closed on holidays."
    assert row.status == BookingStatus.PENDING


def test_module_times_cannot_be_approved_once_the_date_is_an_exam_session(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    response, row = decide(
        db, monkeypatch, make_room(db, None), E, start_time=time(13, 0), end_time=time(14, 30)
    )

    assert response.status_code == 400
    assert row.status == BookingStatus.PENDING


def test_whole_hours_can_be_approved_in_an_exam_session(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    response, _ = decide(
        db, monkeypatch, make_room(db, None), E, start_time=time(13, 0), end_time=time(14, 0)
    )

    assert response.status_code == 200, response.text


def test_a_booking_on_a_holiday_can_still_be_rejected(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    response, row = decide(db, monkeypatch, make_room(db, None), H, decision="reject")

    assert response.status_code == 200
    assert row.status == BookingStatus.REJECTED


# --- bad input, concurrent saves, the last date ---------------------------------------


@pytest.mark.parametrize("start, end", [("10:00Z", "11:00Z"), ("10:00+02:00", "11:00")])
def test_a_time_with_a_time_zone_is_a_422(
    db: Session, monkeypatch: pytest.MonkeyPatch, start: str, end: str
) -> None:
    room = make_room(db, None)
    day = date(2031, 12, 15)
    period(db, E, day, day)
    client = booking_client(db)
    sign_in(db, client, monkeypatch, "sub-tz", "tz@ulbsibiu.ro")

    response = client.post(
        "/api/bookings",
        json={
            "classroom_id": str(room.id),
            "specific_date": day.isoformat(),
            "start_time": start,
            "end_time": end,
            "title": "Study",
        },
    )

    assert response.status_code == 422


def test_checking_a_period_holds_a_lock_until_the_save_ends(db: Session) -> None:
    check_body(
        db,
        PeriodBody(name="A", type=T, start_date=date(2033, 1, 1), end_date=date(2033, 1, 2)),
    )

    with engine.connect() as other, other.begin():
        assert other.scalar(select(func.pg_try_advisory_xact_lock(PERIODS_LOCK))) is False


def test_a_period_may_end_on_the_last_possible_date(db: Session) -> None:
    db.add(AcademicPeriod(name="Always", type=H, start_date=date(9999, 12, 30), end_date=date.max))
    db.flush()

    assert occurrences(db, date(9999, 12, 30), date.max) == []
