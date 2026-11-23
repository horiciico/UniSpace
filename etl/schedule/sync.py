"""Schedule ETL, steps 1 and 2: faculties and the active planning unit of each faculty.

Step 1 stores every faculty in `faculties`; step 2 stores each faculty's active planning unit
(a semester or a module) in `planning_time_units`. Run through `etl.schedule.cli`.
"""

import asyncio
from dataclasses import dataclass
from datetime import date

import httpx
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Faculty, PlanningTimeUnit, PlanningUnitType
from etl.schedule.common import TIMEOUT_SECONDS, format_table

FACULTIES_URL = "https://schedule.ulbsibiu.ro/api/faculties"
PLANNING_UNITS_URL = "https://schedule.ulbsibiu.ro/api/faculties/{code}/planning-time-units"
MAX_CONCURRENT_FACULTIES = 3
# Resolution order: semester first, then module (see fetch_active_planning_unit).
UNIT_TYPES = ("semester", "module")


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

