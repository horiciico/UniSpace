"""ETL downloader for the ULBS schedule API.

Step 1: store every faculty (GET /api/faculties) in `faculties`.
Step 2: store each faculty's active planning unit (a semester or a module) in
        `planning_time_units`.
Step 3: download the weekly schedule of each active planning unit to `data/schedules/`.

Run through the compose profile. One command runs all three steps:
    docker compose --profile etl run --rm etl                          # all faculties, steps 1-3
    docker compose --profile etl run --rm etl --faculty sti            # one faculty, steps 1-3
Partial runs:
    docker compose --profile etl run --rm etl --step sync              # steps 1 and 2 only
    docker compose --profile etl run --rm etl --step schedules         # step 3 only (needs step 2 done)
"""

import argparse
import asyncio
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Faculty, PlanningTimeUnit, PlanningUnitType

FACULTIES_URL = "https://schedule.ulbsibiu.ro/api/faculties"
PLANNING_UNITS_URL = "https://schedule.ulbsibiu.ro/api/faculties/{code}/planning-time-units"
SCHEDULE_URL = "https://schedule.ulbsibiu.ro/api/faculties/{code}/schedule/weekly"
TIMEOUT_SECONDS = 30.0
# The weekly schedule can be several MB and slow to build on the ULBS side.
SCHEDULE_TIMEOUT = httpx.Timeout(connect=15.0, read=300.0, write=15.0, pool=15.0)
MAX_CONCURRENT_FACULTIES = 3
MAX_CONCURRENT_SCHEDULES = 2
# Resolution order: semester first, then module (see fetch_active_planning_unit).
UNIT_TYPES = ("semester", "module")
SCHEDULES_DIR = Path("data/schedules")  # relative to the working directory (/app in the image)
JSON_INDENT = 2  # pretty-printed; checked against the file sizes of the first full run


# --- Output table ------------------------------------------------------------------------

def format_table(headers: tuple[str, ...], rows: list[tuple]) -> str:
    """A plain-text table with one row per item."""
    widths = [max(len(str(cell)) for cell in column) for column in zip(headers, *rows)] if rows else [
        len(h) for h in headers
    ]
    lines = [" | ".join(h.ljust(w) for h, w in zip(headers, widths))]
    lines.append("-+-".join("-" * w for w in widths))
    lines.extend(" | ".join(str(c).ljust(w) for c, w in zip(row, widths)) for row in rows)
    return "\n".join(lines)


# --- Step 1: faculties -------------------------------------------------------------------

async def fetch_faculties(client: httpx.AsyncClient | None = None) -> object:
    """Return the decoded JSON body of GET /api/faculties.

    The response is `{"success", "message", "data": [...]}`; `_data_list` reads `data`.
    Raises httpx.HTTPStatusError on a non-2xx response.
    """
    if client is not None:
        return await _get_json(client, FACULTIES_URL)
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as own_client:
        return await _get_json(own_client, FACULTIES_URL)


async def _get_json(client: httpx.AsyncClient, url: str, params: dict | None = None) -> object:
    response = await client.get(url, params=params)
    response.raise_for_status()
    return response.json()


def _data_list(payload: object) -> list:
    """Return the list from a wrapped `{"data": [...]}` or a raw list payload."""
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    if isinstance(payload, list):
        return payload
    return []


def faculty_rows(payload: object) -> list[dict]:
    """Map the API faculties to `faculties` rows: the API `id` is our `code`."""
    return [{"code": f["id"], "name": f["name"]} for f in _data_list(payload)]


def upsert_faculties(db: Session, payload: object) -> list[str]:
    """Insert or update every faculty by code. Returns the codes stored.

    Re-running the pipeline updates names and creates no duplicates.
    """
    rows = faculty_rows(payload)
    if not rows:
        return []
    stmt = insert(Faculty).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Faculty.code],
        set_={"name": stmt.excluded.name},
    )
    db.execute(stmt)
    db.commit()
    return [row["code"] for row in rows]


# --- Step 2: active planning unit --------------------------------------------------------

@dataclass(frozen=True)
class ActiveUnit:
    unit_type: str  # "semester" or "module", as the API names it
    unit: dict  # the API item


async def fetch_planning_units(
    client: httpx.AsyncClient, faculty_code: str, year: int, unit_type: str
) -> list[dict]:
    """GET the planning units of one type for a faculty and year.

    `active_only` is false on purpose: with `active_only=true` the API returned Modul 2
    (isCurrent false) and left out Modul 1 (isCurrent true), so the selection is done
    locally in `pick_current`.
    """
    payload = await _get_json(
        client,
        PLANNING_UNITS_URL.format(code=faculty_code),
        params={"year": year, "type": unit_type, "active_only": "false", "visible_only": "false"},
    )
    return _data_list(payload)


def _window(unit: dict) -> tuple[date, date] | None:
    """The unit's (startDate, endDate), or None when either is missing or malformed."""
    try:
        return date.fromisoformat(unit["startDate"]), date.fromisoformat(unit["endDate"])
    except (KeyError, TypeError, ValueError):
        return None


def pick_current(units: list[dict], today: date) -> dict | None:
    """The unit flagged `isCurrent`; if none is flagged, the one whose dates contain today."""
    for unit in units:
        if unit.get("isCurrent") is True:
            return unit
    for unit in units:
        window = _window(unit)
        if window is not None and window[0] <= today <= window[1]:
            return unit
    return None


async def fetch_active_planning_unit(
    client: httpx.AsyncClient, faculty_code: str, year: int, today: date | None = None
) -> ActiveUnit | None:
    """Try each unit type in order; return the first one with a current unit, or None."""
    today = today or date.today()
    for unit_type in UNIT_TYPES:
        units = await fetch_planning_units(client, faculty_code, year, unit_type)
        unit = pick_current(units, today)
        if unit is not None:
            return ActiveUnit(unit_type, unit)
    return None


def upsert_planning_unit(db: Session, faculty_id, active: ActiveUnit) -> None:
    """Store the active unit as current and clear the flag on the faculty's other units.

    Re-running updates the same row (faculty_id, external_id): no duplicates.
    The caller commits.
    """
    unit = active.unit
    window = _window(unit)
    if window is None:
        raise ValueError(f"unit {unit.get('id')} has no valid startDate/endDate")
    external_id = int(unit["id"])
    columns = ("year", "name", "display_name", "type", "start_date", "end_date", "is_current")
    values = dict(
        faculty_id=faculty_id,
        external_id=external_id,
        year=int(unit["year"]),
        name=unit["name"],
        display_name=unit.get("displayName"),
        type=PlanningUnitType(active.unit_type.upper()),
        start_date=window[0],
        end_date=window[1],
        is_current=True,
    )
    stmt = insert(PlanningTimeUnit).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[PlanningTimeUnit.faculty_id, PlanningTimeUnit.external_id],
        set_={column: getattr(stmt.excluded, column) for column in columns},
    )
    db.execute(stmt)
    db.execute(
        update(PlanningTimeUnit)
        .where(PlanningTimeUnit.faculty_id == faculty_id, PlanningTimeUnit.external_id != external_id)
        .values(is_current=False)
    )


@dataclass
class SyncResult:
    code: str
    status: str  # "ok", "skipped" or "error"
    unit_type: str = "-"
    external_id: str = "-"
    name: str = "-"
    window: str = "-"
    note: str = ""


async def _sync_faculty(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    faculty_id,
    code: str,
    year: int,
) -> SyncResult:
    async with semaphore:
        try:
            active = await fetch_active_planning_unit(client, code, year)
            if active is None:
                return SyncResult(code, "skipped", note="no current semester or module")
            with SessionLocal() as db:
                upsert_planning_unit(db, faculty_id, active)
                db.commit()
            window = _window(active.unit)
            return SyncResult(
                code, "ok", active.unit_type, str(active.unit["id"]), active.unit["name"],
                f"{window[0]} -> {window[1]}" if window else "-",
            )
        except Exception as exc:  # one faculty must never stop the others
            return SyncResult(code, "error", note=f"{type(exc).__name__}: {exc}")


async def sync_planning_units(faculty_code: str | None = None, year: int | None = None) -> list[SyncResult]:
    """Store the active planning unit of each faculty (all, or the one given).

    Reads the faculties from the database, so run the faculty step first.
    """
    year = year or date.today().year
    with SessionLocal() as db:
        query = select(Faculty.id, Faculty.code).order_by(Faculty.code)
        if faculty_code is not None:
            query = query.where(Faculty.code == faculty_code)
        faculties = db.execute(query).all()

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FACULTIES)
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        results = await asyncio.gather(
            *(_sync_faculty(client, semaphore, faculty_id, code, year) for faculty_id, code in faculties)
        )
    return list(results)


def format_summary(results: list[SyncResult]) -> str:
    headers = ("faculty", "status", "type", "external_id", "name", "active period", "note")
    rows = [(r.code, r.status, r.unit_type, r.external_id, r.name, r.window, r.note) for r in results]
    return format_table(headers, rows)


# --- Step 3: weekly schedules ------------------------------------------------------------

@dataclass(frozen=True)
class CurrentUnit:
    """An `is_current` planning unit, with its faculty code, as the schedule step needs it."""

    faculty_code: str
    db_id: str
    external_id: int
    name: str
    type: str  # "semester" or "module"
    start_date: date
    end_date: date


def load_current_units(db: Session, faculty_code: str | None = None) -> list[CurrentUnit]:
    """The current planning unit of each faculty (or of the one given), joined to its faculty."""
    query = (
        select(PlanningTimeUnit, Faculty.code)
        .join(Faculty, PlanningTimeUnit.faculty_id == Faculty.id)
        .where(PlanningTimeUnit.is_current.is_(True))
        .order_by(Faculty.code)
    )
    if faculty_code is not None:
        query = query.where(Faculty.code == faculty_code)
    return [
        CurrentUnit(
            faculty_code=code,
            db_id=str(unit.id),
            external_id=unit.external_id,
            name=unit.name,
            type=unit.type.value.lower(),
            start_date=unit.start_date,
            end_date=unit.end_date,
        )
        for unit, code in db.execute(query).all()
    ]


def schedule_filename(unit_name: str, faculty_code: str) -> str:
    """`Modul 1` + `sti` -> `modul_1_sti.json`: lower case, letters and digits, underscores."""
    slug = re.sub(r"[^a-z0-9]+", "_", unit_name.lower()).strip("_")
    return f"{slug}_{faculty_code}.json"


def build_envelope(unit: CurrentUnit, schedule: object, fetched_at: str) -> dict:
    """The file the Step 4 parser reads: the planning unit context plus the raw ULBS response."""
    return {
        "faculty_code": unit.faculty_code,
        "planning_time_unit": {
            "db_id": unit.db_id,
            "external_id": unit.external_id,
            "name": unit.name,
            "type": unit.type,
            "start_date": unit.start_date.isoformat(),
            "end_date": unit.end_date.isoformat(),
        },
        "fetched_at": fetched_at,
        "schedule": schedule,
    }


async def fetch_weekly_schedule(client: httpx.AsyncClient, faculty_code: str, external_id: int) -> object:
    """GET the weekly schedule of one planning unit. Raises on HTTP errors and invalid JSON."""
    response = await client.get(
        SCHEDULE_URL.format(code=faculty_code),
        params={"planning_time_unit_id": external_id},
    )
    response.raise_for_status()
    return response.json()  # json.JSONDecodeError is a ValueError


def write_json_atomic(path: Path, document: dict, indent: int | None) -> int:
    """Write UTF-8 JSON to a temporary file, then rename it. Returns the file size in bytes.

    A failed or interrupted write never leaves a half-written file under the final name.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / (path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=indent)
    os.replace(temporary, path)
    return path.stat().st_size


@dataclass
class DownloadResult:
    code: str
    status: str  # "ok" or "error"
    seconds: float = 0.0
    path: str = "-"
    size_kb: float | None = None
    note: str = ""


async def _download_one(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    unit: CurrentUnit,
    output_dir: Path,
    indent: int | None,
) -> DownloadResult:
    async with semaphore:
        started = time.monotonic()
        print(f"[{unit.faculty_code}] start: {unit.name} (external_id {unit.external_id})", flush=True)
        try:
            schedule = await fetch_weekly_schedule(client, unit.faculty_code, unit.external_id)
            fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            path = output_dir / schedule_filename(unit.name, unit.faculty_code)
            size = write_json_atomic(path, build_envelope(unit, schedule, fetched_at), indent)
            elapsed = time.monotonic() - started
            result = DownloadResult(unit.faculty_code, "ok", elapsed, str(path), size / 1024)
        except httpx.TimeoutException as exc:
            result = DownloadResult(unit.faculty_code, "error", time.monotonic() - started,
                                    note=f"timeout: {exc}")
        except httpx.HTTPError as exc:
            result = DownloadResult(unit.faculty_code, "error", time.monotonic() - started,
                                    note=f"HTTP error: {exc}")
        except ValueError as exc:
            result = DownloadResult(unit.faculty_code, "error", time.monotonic() - started,
                                    note=f"invalid JSON: {exc}")
        except OSError as exc:
            result = DownloadResult(unit.faculty_code, "error", time.monotonic() - started,
                                    note=f"file error: {exc}")
        _print_done(result)
        return result


def _print_done(result: DownloadResult) -> None:
    if result.status == "ok":
        print(f"[{result.code}] ok in {result.seconds:.1f} s -> {result.path} ({result.size_kb:.1f} KB)",
              flush=True)
    else:
        print(f"[{result.code}] FAILED after {result.seconds:.1f} s: {result.note}", flush=True)


async def download_schedules(
    faculty_code: str | None = None,
    output_dir: Path = SCHEDULES_DIR,
    indent: int | None = JSON_INDENT,
) -> list[DownloadResult]:
    """Download the weekly schedule of each current planning unit (all, or the one given)."""
    with SessionLocal() as db:
        units = load_current_units(db, faculty_code)
    if not units:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCHEDULES)
    async with httpx.AsyncClient(timeout=SCHEDULE_TIMEOUT) as client:
        results = await asyncio.gather(
            *(_download_one(client, semaphore, unit, output_dir, indent) for unit in units)
        )
    return list(results)


def format_download_summary(results: list[DownloadResult]) -> str:
    headers = ("faculty", "status", "seconds", "size KB", "file", "note")
    rows = [
        (r.code, r.status, f"{r.seconds:.1f}",
         f"{r.size_kb:.1f}" if r.size_kb is not None else "-", r.path, r.note)
        for r in results
    ]
    return format_table(headers, rows)


# --- CLI ---------------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ULBS schedule ETL")
    parser.add_argument("--step", choices=("all", "sync", "schedules"), default="all",
                        help="all = steps 1-3 (default); sync = faculties and planning units; "
                             "schedules = weekly schedule files for the current planning units")
    parser.add_argument("--faculty", help="one faculty code, e.g. sti (default: all faculties)")
    parser.add_argument("--year", type=int, help="academic year (default: the current year)")
    return parser.parse_args(argv)


async def _run_sync(args: argparse.Namespace) -> bool:
    """Steps 1 and 2. Returns False when a requested faculty is not in the database."""
    payload = await fetch_faculties()
    with SessionLocal() as db:
        codes = upsert_faculties(db, payload)
    print("Faculties stored:", len(codes))

    results = await sync_planning_units(args.faculty, args.year)
    if args.faculty and not results:
        print(f"Faculty '{args.faculty}' is not in the database. Known codes: {', '.join(codes)}")
        return False
    print(format_summary(results))
    return True


async def _run_schedules(args: argparse.Namespace) -> bool:
    """Step 3. Returns False when there is no current planning unit to download."""
    results = await download_schedules(args.faculty)
    if not results:
        print(f"No current planning unit found{' for ' + args.faculty if args.faculty else ''}. "
              "Run the sync step first.")
        return False
    print()
    print(format_download_summary(results))
    return True


async def _main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.step in ("all", "sync"):
        if not await _run_sync(args):
            return
    if args.step in ("all", "schedules"):
        if args.step == "all":
            print()
        await _run_schedules(args)


if __name__ == "__main__":
    asyncio.run(_main())
