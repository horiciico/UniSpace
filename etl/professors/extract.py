"""Professors pipeline, step 1 (extract): the professors of each faculty, from the ULBS API to a local file.

Each file `data/professors/<code>.json` keeps only the normalized records (id, name, email) and the
records skipped, with the reason. Step 2 (`load.py`) reads these files. Run through `etl.professors.cli`.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

from etl.common import write_json_atomic

PROFESSORS_URL = "https://schedule.ulbsibiu.ro/api/faculties/{code}/professors"
PER_PAGE = 500
TIMEOUT_SECONDS = 30.0
PROFESSORS_DIR = Path("data/professors")  # relative to the working directory (/app in the image)
JSON_INDENT = 2


def normalize(raw: object) -> tuple[dict | None, str | None]:
    """The stored fields of one API record, or (None, reason) when the record is skipped.

    Keeps id, name and email only. The email is stripped and lower-cased; a null, empty or
    blank email is skipped (the admin handles those by hand).
    """
    if not isinstance(raw, dict):
        return None, "not an object"
    try:
        professor_id = str(uuid.UUID(str(raw.get("id"))))
    except ValueError:
        return None, "id is not a UUID"
    email = raw.get("email")
    if not isinstance(email, str) or not email.strip():
        return None, "no email"
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        return None, "no name"
    return {"id": professor_id, "name": name.strip(), "email": email.strip().lower()}, None


async def fetch_faculty_pages(client: httpx.AsyncClient, code: str) -> list[dict]:
    """Every record of one faculty: pages 1 up to `pagination.last_page`, 500 per page."""
    items: list[dict] = []
    page, last = 1, 1
    while page <= last:
        response = await client.get(
            PROFESSORS_URL.format(code=code),
            params={"page": page, "per_page": PER_PAGE, "with_exams_only": "false"},
        )
        response.raise_for_status()
        body = response.json()
        items.extend(body.get("data") or [])
        last = (body.get("pagination") or {}).get("last_page", 1)
        page += 1
    return items


@dataclass
class ExtractResult:
    code: str
    status: str  # "ok" or "error"
    stored: int = 0
    skipped: int = 0
    path: str = "-"
    note: str = ""


async def extract_faculty(client: httpx.AsyncClient, code: str, output_dir: Path) -> ExtractResult:
    """Fetch one faculty and write its file. A failure is reported and writes nothing."""
    try:
        items = await fetch_faculty_pages(client, code)
    except httpx.HTTPError as exc:
        return ExtractResult(code, "error", note=f"HTTP error: {exc}")
    except ValueError as exc:
        return ExtractResult(code, "error", note=f"invalid JSON: {exc}")

    professors: list[dict] = []
    skipped: list[dict] = []
    for raw in items:
        record, reason = normalize(raw)
        if record is None:
            skipped.append({"id": raw.get("id") if isinstance(raw, dict) else None, "reason": reason})
        else:
            professors.append(record)

    document = {
        "faculty_code": code,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "professors": professors,
        "skipped": skipped,
    }
    path = output_dir / f"{code}.json"
    try:
        write_json_atomic(path, document, JSON_INDENT)
    except OSError as exc:
        return ExtractResult(code, "error", note=f"file error: {exc}")
    return ExtractResult(code, "ok", stored=len(professors), skipped=len(skipped), path=str(path))


async def extract_faculties(
    codes: list[str],
    output_dir: Path = PROFESSORS_DIR,
    transport: httpx.AsyncBaseTransport | None = None,
) -> list[ExtractResult]:
    """Extract each faculty in turn. One faculty's failure does not stop the others."""
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport) as client:
        return [await extract_faculty(client, code, output_dir) for code in codes]
