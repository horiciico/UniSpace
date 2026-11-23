"""Schedule ETL, step 3: download the weekly schedule of each current planning unit.

Writes one JSON file per unit to `data/schedules/` (the step 4 loader reads them). Run through
`etl.schedule.cli`.
"""

import asyncio
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Faculty, PlanningTimeUnit
from etl.common import write_json_atomic
from etl.schedule.common import format_table

SCHEDULE_URL = "https://schedule.ulbsibiu.ro/api/faculties/{code}/schedule/weekly"
# The weekly schedule can be several MB and slow to build on the ULBS side.
SCHEDULE_TIMEOUT = httpx.Timeout(connect=15.0, read=300.0, write=15.0, pool=15.0)
MAX_CONCURRENT_SCHEDULES = 2
SCHEDULES_DIR = Path("data/schedules")  # relative to the working directory (/app in the image)
JSON_INDENT = 2  # pretty-printed; checked against the file sizes of the first full run


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

