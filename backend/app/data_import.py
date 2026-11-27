"""The admin's data import (D-031): the schedule pipeline, then the professors pipeline (etl/), in
a background thread.

One run at a time. The state of the last run is kept in memory, so a restart forgets it. Each run
downloads into its own temporary folder and loads only those files, so a file left by an earlier
run or an older planning unit is never read. The pipelines update and never delete; afterwards the
run lists the imported classes that clash with an approved booking, a moved class or an exam.

Error texts of a failed save can hold email addresses, so none is returned or logged.
"""

import asyncio
import logging
import tempfile
import threading
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db import SessionLocal
from app.models import (
    Activity,
    ActivityGroup,
    ActivityType,
    Booking,
    BookingStatus,
    Classroom,
    Status,
)
from app.planning import Occurrence, hhmm, local_today, occurrences
from etl.professors.extract import extract_faculties
from etl.professors.load import load_professors
from etl.schedule.download import download_schedules
from etl.schedule.loader import load_all
from etl.schedule.sync import fetch_faculties, sync_planning_units, upsert_faculties

logger = logging.getLogger(__name__)

_IDLE = {
    "status": "idle",
    "step": None,
    "started_at": None,
    "finished_at": None,
    "result": None,
}
_lock = threading.Lock()
_state: dict = dict(_IDLE)
_thread: threading.Thread | None = None


def state() -> dict:
    """A copy of the state of the current or last run."""
    with _lock:
        return dict(_state)


def _update(**values) -> None:
    with _lock:
        _state.update(values)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def start() -> bool:
    """Starts a run in the background. False when one is already going."""
    global _thread
    with _lock:
        if _state["status"] == "running":
            return False
        _state.update(_IDLE, status="running", started_at=_now())
        _thread = threading.Thread(target=_work, daemon=True)
        _thread.start()
    return True


def wait(seconds: float) -> None:
    if _thread is not None:
        _thread.join(seconds)


def reset() -> None:
    """Forgets the last run (tests)."""
    _update(**_IDLE)


def _work() -> None:
    try:
        with tempfile.TemporaryDirectory() as folder:
            result = asyncio.run(run_pipeline(Path(folder), lambda step: _update(step=step)))
        _update(status="done", step=None, result=result, finished_at=_now())
    except Exception as exc:  # the thread must always leave the "running" state
        logger.error("data import failed at %s: %s", state()["step"], type(exc).__name__)
        _update(status="failed", finished_at=_now())


async def run_pipeline(folder: Path, step: Callable[[str], None]) -> dict:
    """The whole import. A faculty that fails is listed and left as it is; the others go on."""
    step("faculties")
    payload = await fetch_faculties()
    with SessionLocal() as db:
        codes = upsert_faculties(db, payload)

    step("planning_units")
    synced = await sync_planning_units()

    step("schedules")
    schedules = folder / "schedules"
    downloads = await download_schedules(None, schedules)

    step("timetable")
    report = await load_all(None, schedules)

    step("professors")
    professors_folder = folder / "professors"
    extracted = await extract_faculties(codes, professors_folder)
    professors = load_professors(
        professors_folder, complete=all(r.status == "ok" for r in extracted)
    )

    step("clashes")
    with SessionLocal() as db:
        clashes = find_clashes(db, local_today())

    problems = [
        *({"faculty": r.code, "kind": "planning"} for r in synced if r.status == "error"),
        *({"faculty": r.code, "kind": "download"} for r in downloads if r.status != "ok"),
        *({"faculty": code, "kind": "empty"} for code in report.empty),
        *({"faculty": code, "kind": "load"} for code in report.failed),
        *({"faculty": r.code, "kind": "professors"} for r in extracted if r.status != "ok"),
    ]
    if professors.errors or professors.email_conflicts:
        problems.append({"faculty": None, "kind": "professors_save"})
    return {
        "schedule": {
            "inserted": report.inserted,
            "updated": report.updated,
            "unchanged": report.unchanged,
            "restored": report.restored,
            "cancelled": report.cancelled,
            "kept_edited": report.skipped_manual,
            "unread_entries": len(report.unparsed),
        },
        "professors": {"stored": professors.stored},
        "problems": problems,
        "clashes": clashes,
    }


def _groups(db: Session, activity_id) -> set:
    return set(
        db.scalars(
            select(ActivityGroup.group_id).where(ActivityGroup.activity_id == activity_id)
        ).all()
    )


def find_clashes(db: Session, first: date) -> list[dict]:
    """From `first` on: the approved bookings, moved classes and exams that overlap an imported
    weekly class. A booking clashes by room; a moved class or exam also by professor or group."""
    imported: dict[date, list[Occurrence]] = {}

    def classes_on(day: date) -> list[Occurrence]:
        if day not in imported:
            imported[day] = occurrences(
                db, day, day, Activity.external_id.is_not(None), Activity.specific_date.is_(None)
            )
        return imported[day]

    found: list[dict] = []

    def check(day, start, end, room, what, title, professor_id=None, groups=frozenset()) -> None:
        for other in classes_on(day):
            from_time = other.start_time or other.activity.start_time
            to_time = other.end_time or other.activity.end_time
            if not (from_time < end and start < to_time):
                continue
            reasons = []
            if other.activity.classroom_id == room.id:
                reasons.append("room")
            if professor_id is not None and other.activity.professor_id == professor_id:
                reasons.append("professor")
            if groups and groups & _groups(db, other.activity.id):
                reasons.append("group")
            if not reasons:
                continue
            found.append(
                {
                    "date": day.isoformat(),
                    "start": hhmm(start),
                    "end": hhmm(end),
                    "room": room.name,
                    "what": what,
                    "title": title,
                    "class_start": hhmm(from_time),
                    "class_end": hhmm(to_time),
                    "class_room": other.activity.classroom.name,
                    "reasons": reasons,
                }
            )

    bookings = db.execute(
        select(Booking, Classroom)
        .join(Classroom, Classroom.id == Booking.classroom_id)
        .where(Booking.status == BookingStatus.APPROVED, Booking.specific_date >= first)
    ).all()
    for booking, room in bookings:
        check(
            booking.specific_date,
            booking.start_time,
            booking.end_time,
            room,
            "booking",
            booking.title,
        )
    one_offs = db.scalars(
        select(Activity)
        .options(joinedload(Activity.classroom))
        .where(
            Activity.specific_date >= first,
            Activity.external_id.is_(None),
            Activity.status != Status.CANCELLED,
        )
    ).all()
    for one_off in one_offs:
        check(
            one_off.specific_date,
            one_off.start_time,
            one_off.end_time,
            one_off.classroom,
            "exam" if one_off.type == ActivityType.EXAM else "class",
            one_off.name,
            one_off.professor_id,
            _groups(db, one_off.id),
        )
    return sorted(found, key=lambda c: (c["date"], c["start"], c["room"]))
