"""Professors pipeline, step 2 (load): upsert the files in `data/professors/` into `professors`.

One person is one email (D-019). Records that share a normalized email are one professor: one id is
kept, the others are left out and logged as warnings. The kept id is, in order: the id already stored
for that email, then an id used by an activity, then the smallest id.

If the API drops the stored id and gives the same email a new id, the stored row takes the new id, and
the users and activities that pointed at the old id are moved to the new one. This needs a full run
(all faculties, every file readable); a partial run only reports the refusal.

Otherwise idempotent: a professor is inserted, or updated by id. Nothing is deleted, so a professor
missing from the latest files stays in the table. Emails are not printed or logged.
Run through `etl.professors.cli`.
"""

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Activity, Professor, User
from etl.professors.extract import PROFESSORS_DIR


@dataclass
class LoadReport:
    files: list[str] = field(default_factory=list)
    records: int = 0  # distinct professors after the merge
    repeated_ids: int = 0  # the same id seen again in another file (another faculty)
    merged_emails: int = 0  # records left out: the same email as a kept record
    rekeyed: list[tuple[str, str]] = field(default_factory=list)  # (old id, new id) for the same email
    stored: int = 0  # inserted or updated
    email_conflicts: list[str] = field(default_factory=list)  # ids the database refused (email held by another id)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class MergeResult:
    records: list[dict]  # one per normalized email, sorted by id
    repeated_ids: int
    dropped: list[tuple[str, str]]  # (id left out, id kept), for each record that shares an email


def normalize_email(email: str) -> str:
    return email.strip().lower()


def merge_records(
    docs: list[tuple[str, dict]],
    stored: dict[str, str] | None = None,
    used: set[str] | None = None,
) -> MergeResult:
    """Merge the records of all files into one record per person (per normalized email).

    `stored` maps an email to the id already in the table; `used` holds the ids of activities.
    Within an email the id kept is the stored one, else one used by an activity, else the smallest id.
    """
    stored = stored or {}
    used = used or set()
    by_id: dict[str, dict] = {}
    repeated = 0
    for _name, doc in docs:
        for record in doc.get("professors") or []:
            if record["id"] in by_id:
                repeated += 1
            else:
                by_id[record["id"]] = {**record, "email": normalize_email(record["email"])}

    by_email: dict[str, list[dict]] = {}
    for record in by_id.values():
        by_email.setdefault(record["email"], []).append(record)

    def rank(record: dict) -> int:
        if stored.get(record["email"]) == record["id"]:
            return 0
        return 1 if record["id"] in used else 2

    records: list[dict] = []
    dropped: list[tuple[str, str]] = []
    for email in sorted(by_email):
        members = sorted(by_email[email], key=lambda r: (rank(r), r["id"]))
        keep = members[0]
        records.append(keep)
        dropped.extend((member["id"], keep["id"]) for member in members[1:])
    records.sort(key=lambda r: r["id"])
    return MergeResult(records, repeated, dropped)


def plan_rekeys(records: list[dict], stored: dict[str, str], seen_ids: set[str]) -> list[tuple[str, str]]:
    """(old id, new id) for each kept record whose email is stored under an id no file holds any more."""
    pairs = []
    for record in records:
        old = stored.get(record["email"])
        if old is not None and old != record["id"] and old not in seen_ids:
            pairs.append((old, record["id"]))
    return pairs


def build_preferences(db: Session) -> tuple[dict[str, str], set[str]]:
    """The id already stored for each email, and the professor ids that activities use."""
    stored = {email: str(pid) for pid, email in db.execute(select(Professor.id, Professor.email)).all()}
    used = {
        str(pid)
        for pid in db.scalars(
            select(Activity.professor_id).where(Activity.professor_id.is_not(None)).distinct()
        ).all()
    }
    return stored, used


def read_documents(directory: Path, faculty: str | None = None) -> tuple[list[tuple[str, dict]], list[str]]:
    """The parsed files in name order (all, or the one faculty), and the files that could not be read."""
    docs: list[tuple[str, dict]] = []
    errors: list[str] = []
    for path in sorted(directory.glob("*.json")):
        if faculty is not None and path.stem != faculty:
            continue
        try:
            docs.append((path.name, json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError) as exc:
            errors.append(f"{path.name}: cannot read ({type(exc).__name__}: {exc})")
    return docs, errors


def rekey_professor(db: Session, old_id: str, new_id: str) -> None:
    """Move a professor row to a new id, and the users and activities that pointed at the old one."""
    old, new = uuid.UUID(old_id), uuid.UUID(new_id)
    db.execute(update(Professor).where(Professor.id == old).values(id=new))
    db.execute(update(User).where(User.professor_id == old).values(professor_id=new))
    db.execute(update(Activity).where(Activity.professor_id == old).values(professor_id=new))


def upsert_professors(db: Session, records: list[dict], report: LoadReport) -> None:
    """Insert or update each record by id. Does not commit: the caller does."""
    for record in records:
        values = {"id": uuid.UUID(record["id"]), "name": record["name"], "email": record["email"]}
        stmt = insert(Professor).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Professor.id],
            set_={"name": stmt.excluded.name, "email": stmt.excluded.email},
        )
        try:
            with db.begin_nested():
                db.execute(stmt)
        except IntegrityError:  # the email is held by another id in the table; the rest still load
            report.email_conflicts.append(record["id"])
            continue
        report.stored += 1


def sync_professors(db: Session, docs: list[tuple[str, dict]], full_run: bool, report: LoadReport) -> None:
    """Merge the documents per person, move re-keyed rows (full runs only), then upsert. No commit."""
    stored, used = build_preferences(db)
    merged = merge_records(docs, stored, used)
    report.records = len(merged.records)
    report.repeated_ids = merged.repeated_ids
    report.merged_emails = len(merged.dropped)
    report.warnings.extend(
        f"duplicate email: id {dropped} left out, id {kept} kept" for dropped, kept in merged.dropped
    )
    if full_run:
        seen = {record["id"] for _, doc in docs for record in doc.get("professors") or []}
        for old, new in plan_rekeys(merged.records, stored, seen):
            rekey_professor(db, old, new)
            report.rekeyed.append((old, new))
            report.warnings.append(f"id {old} replaced by id {new} (same email); users and activities moved")
    upsert_professors(db, merged.records, report)


def load_professors(
    directory: Path = PROFESSORS_DIR, faculty: str | None = None, complete: bool = True
) -> LoadReport:
    """Read the files (all, or one faculty) and sync them in one commit.

    A run counts as full only when it covers every faculty and every file could be read.
    `complete=False` says that a faculty's file is missing, so the run is not full.
    """
    report = LoadReport()
    docs, errors = read_documents(directory, faculty)
    report.errors.extend(errors)
    report.files = [name for name, _ in docs]
    full_run = complete and faculty is None and not errors
    try:
        with SessionLocal() as db:
            sync_professors(db, docs, full_run, report)
            db.commit()
    except SQLAlchemyError as exc:
        report.stored = 0
        report.rekeyed = []
        report.errors.append(f"database error: {type(exc).__name__}: {exc}")
    return report
