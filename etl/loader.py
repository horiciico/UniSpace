"""Step 4: load the weekly schedule files into PostgreSQL.

Reads data/schedules/*.json (written by step 3) and writes:
- classrooms: one row per ULBS room id. Capacity is NULL when the ULBS rooms list has none.
- student_groups: one row per ULBS studyFormation id.
- activities: one row per (room, day, parity, start, end). Every entry that falls in the same
  row becomes that one row. Every stored row is named "Didactic Activity" with priority 5.

Rules:
- an entry with no room, or an online entry, is not stored
- rows edited by an admin (is_manually_modified) are never changed
- a row of the planning unit that no longer appears in the feed is deleted, unless an
  exception or a change request points at it (those rows are kept and reported)
- a file that cannot be read or loaded is reported and does not stop the other files

Run through the compose profile (or as step 4 of the full pipeline):
    docker compose --profile etl run --rm etl --step load
    docker compose --profile etl run --rm etl --step load --faculty ing
"""

import argparse
import asyncio
import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    Activity,
    ActivityException,
    ActivityType,
    Classroom,
    Faculty,
    Parity,
    PlanningTimeUnit,
    Priority,
    RuleChangeRequest,
    Status,
    StudentGroup,
)
from etl.downloader import SCHEDULES_DIR, TIMEOUT_SECONDS

# The path's faculty is ignored by the API; `?faculty=` selects the owning faculty's rooms.
# Owner-less rooms only appear in the list without the parameter, so both are read.
ROOMS_URL = "https://schedule.ulbsibiu.ro/api/faculties/ing/rooms"

DAY_NUMBERS = {
    "Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4,
    "Friday": 5, "Saturday": 6, "Sunday": 7,  # ISO, Monday = 1 (D-008)
}
PARITY_BY_API = {0: Parity.ALL, 1: Parity.ODD, 2: Parity.EVEN}  # D-014
# Mapped by name: the ULBS ids repeat across names (for example two ids are both "Curs").
ACTIVITY_TYPE_BY_NAME = {
    "Curs": ActivityType.COURSE,
    "Seminar": ActivityType.SEMINAR,
    "Laborator": ActivityType.LAB,
    "Proiect": ActivityType.LAB,
    "Practica": ActivityType.LAB,
    "L.Pr.": ActivityType.LAB,
    "Tutorat": ActivityType.SEMINAR,
    "Facultativ": ActivityType.COURSE,
    "C+S": ActivityType.COURSE,
}
# When one row merges entries of several types, the first type in this order is kept.
TYPE_PRECEDENCE = (ActivityType.COURSE, ActivityType.LAB, ActivityType.SEMINAR)
DIDACTIC_ACTIVITY_NAME = "Didactic Activity"
DIDACTIC_PRIORITY = Priority.COURSE  # 5: every planned activity (D-007, answer 6)
ONLINE_PATTERN = re.compile(r"online|meet\.google\.com|zoom\.us|https?://", re.IGNORECASE)
CLASSROOM_NAME_MAX = 50
GROUP_NAME_MAX = 50
PROFESSOR_MAX = 255


class NotStored(Exception):
    """An entry that is left out on purpose: no room, or an online class."""


class Unparsed(Exception):
    """An entry that cannot be read. Reported with the reason."""


@dataclass(frozen=True)
class Block:
    """One contiguous time block of one ULBS entry, ready to be grouped."""

    item_id: int
    subject: str
    room_id: str
    room_name: str
    room_faculty: str | None
    day: int
    parity: Parity
    start: time
    end: time
    activity_type: ActivityType
    group_id: int
    group_name: str
    professor: str | None


GroupKey = tuple[str, int, Parity, time, time]


def merge_contiguous(pairs: list[tuple[time, time]]) -> list[tuple[time, time]]:
    """Join slots that touch or overlap. A gap starts a new block (the gap is not covered)."""
    merged: list[tuple[time, time]] = []
    for start, end in sorted(pairs):
        if end <= start:
            raise Unparsed(f"time slot ends before it starts ({start}-{end})")
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def parse_item(item: dict) -> list[Block]:
    """Read one ULBS entry. Raises NotStored or Unparsed; returns one Block per time block."""
    room_id = item.get("roomId")
    room_name = item.get("room") or ""
    if not room_id:
        raise NotStored("no room")
    if ONLINE_PATTERN.search(room_name):
        raise NotStored("online class")

    day = DAY_NUMBERS.get(item.get("day"))
    if day is None:
        raise Unparsed(f"unknown day {item.get('day')!r}")
    parity = PARITY_BY_API.get(item.get("parity"))
    if parity is None:
        raise Unparsed(f"unknown parity {item.get('parity')!r}")
    type_name = (item.get("activityType") or {}).get("name")
    activity_type = ACTIVITY_TYPE_BY_NAME.get(type_name)
    if activity_type is None:
        raise Unparsed(f"unknown activity type {type_name!r}")

    slots = item.get("timeSlots") or []
    if not slots:
        raise Unparsed("no time slots")
    pairs: list[tuple[time, time]] = []
    for slot in slots:
        try:
            pairs.append((time.fromisoformat(slot["startTime"]), time.fromisoformat(slot["endTime"])))
        except (KeyError, TypeError, ValueError):
            raise Unparsed(f"bad time slot {slot!r}") from None
    blocks = merge_contiguous(pairs)

    group = item.get("studyFormation") or {}
    group_id = group.get("id")
    if not isinstance(group_id, int):
        raise Unparsed("no study formation id")
    group_name = (group.get("name") or "")[:GROUP_NAME_MAX]
    professor = item.get("professor") or None

    return [
        Block(
            item_id=item.get("id"),
            subject=item.get("subject") or "",
            room_id=room_id,
            room_name=room_name,
            room_faculty=item.get("roomFacultyId"),
            day=day,
            parity=parity,
            start=start,
            end=end,
            activity_type=activity_type,
            group_id=group_id,
            group_name=group_name,
            professor=professor,
        )
        for start, end in blocks
    ]


def group_blocks(blocks: list[Block]) -> dict[GroupKey, list[Block]]:
    """Every block with the same (room, day, parity, start, end) is one activity row."""
    groups: dict[GroupKey, list[Block]] = {}
    for block in blocks:
        key = (block.room_id, block.day, block.parity, block.start, block.end)
        groups.setdefault(key, []).append(block)
    return groups


def external_id_for(key: GroupKey) -> str:
    """A stable id for a group: the same slot gives the same id on every run (40 characters)."""
    room_id, day, parity, start, end = key
    raw = f"{room_id}|{day}|{parity.value}|{start.isoformat()}|{end.isoformat()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def activity_values(members: list[Block]) -> dict:
    """The stored fields of one activity row, built from the entries it merges."""
    first = min(members, key=lambda b: (b.group_id, b.item_id or 0))
    types = {b.activity_type for b in members}
    professors = sorted({b.professor for b in members if b.professor})
    return {
        "name": DIDACTIC_ACTIVITY_NAME,
        "type": next(t for t in TYPE_PRECEDENCE if t in types),
        "priority": DIDACTIC_PRIORITY,
        "room_id": first.room_id,
        "group_api_id": first.group_id,
        "group_name": first.group_name,
        "day_of_week": first.day,
        "start_time": first.start,
        "end_time": first.end,
        "parity": first.parity,
        "professor_name": (" / ".join(professors))[:PROFESSOR_MAX] or None,
    }


# --- ULBS rooms --------------------------------------------------------------------------

@dataclass(frozen=True)
class RoomInfo:
    name: str
    capacity: int | None
    owner: str | None  # the owning faculty code, or None for rooms with no owner


def rooms_from_pages(pages: list[list[dict]]) -> dict[str, RoomInfo]:
    rooms: dict[str, RoomInfo] = {}
    for page in pages:
        for raw in page:
            capacity = raw.get("capacity")
            rooms[raw["id"]] = RoomInfo(
                name=raw.get("name") or "",
                capacity=capacity if isinstance(capacity, int) and capacity > 0 else None,
                owner=raw.get("faculty"),
            )
    return rooms


async def fetch_rooms(client: httpx.AsyncClient, faculty_codes: list[str]) -> dict[str, RoomInfo]:
    """All rooms: the list without a faculty, plus each faculty's list. Any HTTP error aborts."""
    queries: list[dict] = [{}] + [{"faculty": code} for code in faculty_codes]
    pages: list[list[dict]] = []
    for query in queries:
        page, last = 1, 1
        while page <= last:
            response = await client.get(ROOMS_URL, params={**query, "page": page})
            response.raise_for_status()
            body = response.json()
            pages.append(body["data"])
            last = (body.get("pagination") or {}).get("last_page", 1)
            page += 1
    return rooms_from_pages(pages)


# --- Database writes ---------------------------------------------------------------------

@dataclass
class LoadContext:
    """What one run reuses across files: rooms from the API, faculty ids, and rows already upserted."""

    rooms: dict[str, RoomInfo]
    faculty_ids: dict[str, uuid.UUID]
    classroom_ids: dict[str, uuid.UUID] = field(default_factory=dict)
    group_ids: dict[int, uuid.UUID] = field(default_factory=dict)

    def forget_unsaved(self) -> None:
        """After a failed file the rollback removed the rows, so drop the cached ids."""
        self.classroom_ids.clear()
        self.group_ids.clear()


@dataclass
class LoadReport:
    files_loaded: list[str] = field(default_factory=list)
    entries: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped_manual: int = 0
    deleted: int = 0
    kept_referenced: int = 0
    deduplicated: int = 0
    no_room: int = 0
    unparsed: list[tuple[str, object, str, str]] = field(default_factory=list)  # file, id, subject, reason
    errors: list[str] = field(default_factory=list)
    rooms_stored: int = 0
    rooms_unknown_capacity: int = 0
    rooms_missing_from_api: int = 0
    groups_stored: int = 0
    truncated_names: int = 0


def upsert_classroom(db: Session, ctx: LoadContext, room_id: str, fallback: Block,
                     report: LoadReport) -> uuid.UUID:
    if room_id in ctx.classroom_ids:
        return ctx.classroom_ids[room_id]

    info = ctx.rooms.get(room_id)
    if info is not None:
        name, capacity, owner = info.name, info.capacity, info.owner
    else:
        # Not in the rooms list: take the name and owner from the schedule entry, capacity unknown.
        name, capacity, owner = fallback.room_name, None, fallback.room_faculty
        report.rooms_missing_from_api += 1
    if len(name) > CLASSROOM_NAME_MAX:
        name = name[:CLASSROOM_NAME_MAX]
        report.truncated_names += 1
    faculty_id = ctx.faculty_ids.get(owner) if owner else None

    room = db.scalar(select(Classroom).where(Classroom.external_id == room_id))
    if room is None:
        room = Classroom(external_id=room_id, name=name, capacity=capacity, faculty_id=faculty_id)
        db.add(room)
    else:
        room.name = name
        room.capacity = capacity
        room.faculty_id = faculty_id
    db.flush()

    ctx.classroom_ids[room_id] = room.id
    report.rooms_stored += 1
    if capacity is None:
        report.rooms_unknown_capacity += 1
    return room.id


def upsert_group(db: Session, ctx: LoadContext, api_id: int, name: str, report: LoadReport) -> uuid.UUID:
    if api_id in ctx.group_ids:
        return ctx.group_ids[api_id]
    group = db.scalar(select(StudentGroup).where(StudentGroup.external_id == api_id))
    if group is None:
        group = StudentGroup(external_id=api_id, name=name)
        db.add(group)
    else:
        group.name = name
    db.flush()
    ctx.group_ids[api_id] = group.id
    report.groups_stored += 1
    return group.id


def upsert_activity(db: Session, unit_id: uuid.UUID, external_id: str, values: dict,
                    classroom_id: uuid.UUID, group_id: uuid.UUID, report: LoadReport) -> None:
    target = {
        "name": values["name"],
        "type": values["type"],
        "priority": values["priority"],
        "classroom_id": classroom_id,
        "group_id": group_id,
        "day_of_week": values["day_of_week"],
        "start_time": values["start_time"],
        "end_time": values["end_time"],
        "parity": values["parity"],
        "professor_name": values["professor_name"],
    }
    existing = db.scalar(
        select(Activity).where(
            Activity.planning_time_unit_id == unit_id,
            Activity.external_id == external_id,
        )
    )
    if existing is None:
        db.add(Activity(
            planning_time_unit_id=unit_id,
            external_id=external_id,
            specific_date=None,
            is_manually_modified=False,
            status=Status.APPROVED,
            user_id=None,
            **target,
        ))
        report.inserted += 1
        return
    if existing.is_manually_modified:
        report.skipped_manual += 1
        return
    changed = False
    for name, value in target.items():
        if getattr(existing, name) != value:
            setattr(existing, name, value)
            changed = True
    if changed:
        report.updated += 1
    else:
        report.unchanged += 1


def remove_stale(db: Session, unit_id: uuid.UUID, seen: set[str], report: LoadReport) -> None:
    """Delete ETL rows of this planning unit that are no longer in the feed.

    Admin-edited rows, one-off rows and rows with an exception or a change request stay.
    """
    rows = db.scalars(
        select(Activity).where(
            Activity.planning_time_unit_id == unit_id,
            Activity.external_id.is_not(None),
            Activity.specific_date.is_(None),
            Activity.is_manually_modified.is_(False),
        )
    ).all()
    for row in rows:
        if row.external_id in seen:
            continue
        has_exception = db.scalar(
            select(ActivityException.id).where(ActivityException.activity_id == row.id).limit(1)
        ) is not None
        has_request = db.scalar(
            select(RuleChangeRequest.id).where(RuleChangeRequest.activity_id == row.id).limit(1)
        ) is not None
        if has_exception or has_request:
            report.kept_referenced += 1
            continue
        db.delete(row)
        report.deleted += 1
    db.flush()


def load_envelope(db: Session, envelope: dict, ctx: LoadContext, report: LoadReport, source: str) -> None:
    """Load one schedule file. Raises if the file does not match the database; the caller rolls back."""
    faculty_code = envelope["faculty_code"]
    unit_info = envelope["planning_time_unit"]
    unit = db.get(PlanningTimeUnit, uuid.UUID(unit_info["db_id"]))
    if unit is None:
        raise ValueError("planning unit is not in the database; run the sync step first")
    if unit.faculty_id != ctx.faculty_ids.get(faculty_code):
        raise ValueError(f"planning unit belongs to another faculty than {faculty_code!r}")

    blocks: list[Block] = []
    for day_items in envelope["schedule"]["data"].values():
        for item in day_items:
            report.entries += 1
            try:
                blocks.extend(parse_item(item))
            except NotStored:
                report.no_room += 1
            except Unparsed as exc:
                report.unparsed.append((source, item.get("id"), item.get("subject") or "", str(exc)))

    groups = group_blocks(blocks)
    report.deduplicated += len(blocks) - len(groups)

    seen: set[str] = set()
    for key, members in groups.items():
        external_id = external_id_for(key)
        seen.add(external_id)
        values = activity_values(members)
        try:
            with db.begin_nested():
                classroom_id = upsert_classroom(db, ctx, values["room_id"], members[0], report)
                group_id = upsert_group(db, ctx, values["group_api_id"], values["group_name"], report)
                upsert_activity(db, unit.id, external_id, values, classroom_id, group_id, report)
        except Exception as exc:  # one bad row must not stop the file
            report.unparsed.append((source, members[0].item_id, members[0].subject,
                                    f"database error: {type(exc).__name__}: {exc}"))

    remove_stale(db, unit.id, seen, report)
    db.commit()
    report.files_loaded.append(source)


# --- Run ---------------------------------------------------------------------------------

def read_envelopes(schedules_dir: Path, faculty_code: str | None, report: LoadReport) -> list[tuple[str, dict]]:
    envelopes: list[tuple[str, dict]] = []
    for path in sorted(schedules_dir.glob("*.json")):
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            report.errors.append(f"{path.name}: cannot read ({type(exc).__name__}: {exc})")
            continue
        if faculty_code is not None and envelope.get("faculty_code") != faculty_code:
            continue
        envelopes.append((path.name, envelope))
    return envelopes


async def load_all(faculty_code: str | None = None, schedules_dir: Path = SCHEDULES_DIR) -> LoadReport:
    report = LoadReport()
    envelopes = read_envelopes(schedules_dir, faculty_code, report)
    if not envelopes:
        return report

    with SessionLocal() as db:
        faculties = db.execute(select(Faculty.id, Faculty.code)).all()
    faculty_ids = {code: fid for fid, code in faculties}

    # Rooms are fetched once, before any write: without them capacities would be wrong.
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        rooms = await fetch_rooms(client, sorted(faculty_ids))

    ctx = LoadContext(rooms=rooms, faculty_ids=faculty_ids)
    with SessionLocal() as db:
        for source, envelope in envelopes:
            try:
                load_envelope(db, envelope, ctx, report, source)
            except Exception as exc:
                db.rollback()
                ctx.forget_unsaved()
                report.errors.append(f"{source}: {type(exc).__name__}: {exc}")
    return report


def format_report(report: LoadReport) -> str:
    lines = [
        f"files loaded: {len(report.files_loaded)}   errors: {len(report.errors)}",
        f"entries read: {report.entries}",
        f"activities: inserted {report.inserted}, updated {report.updated}, unchanged {report.unchanged}, "
        f"skipped (admin-edited) {report.skipped_manual}, deleted {report.deleted}, "
        f"kept (exception or request) {report.kept_referenced}",
        f"deduplicated (entries merged into existing rows): {report.deduplicated}",
        f"not stored, no room or online: {report.no_room}",
        f"classrooms stored: {report.rooms_stored} (unknown capacity: {report.rooms_unknown_capacity}, "
        f"not in the rooms list: {report.rooms_missing_from_api})",
        f"student groups stored: {report.groups_stored}",
        f"names truncated to fit: {report.truncated_names}",
    ]
    if report.errors:
        lines.append("")
        lines.append("file errors:")
        lines.extend(f"  {error}" for error in report.errors)
    if report.unparsed:
        lines.append("")
        lines.append(f"unparsed entries: {len(report.unparsed)}")
        for source, item_id, subject, reason in report.unparsed:
            lines.append(f"  {source} | id {item_id} | {subject} | {reason}")
    return "\n".join(lines)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load the schedule files into PostgreSQL")
    parser.add_argument("--faculty", help="only this faculty's files, e.g. ing")
    return parser.parse_args(argv)


async def _main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    report = await load_all(args.faculty)
    if not report.files_loaded and not report.errors:
        print("No schedule files found in data/schedules. Run the schedules step first.")
        return
    print(format_report(report))


if __name__ == "__main__":
    asyncio.run(_main())
