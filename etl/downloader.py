"""ETL downloader for the ULBS schedule API.

Step 1: fetch GET /api/faculties and store every faculty in the `faculties` table.
Run through the compose profile: `docker compose --profile etl run --rm etl`.
"""

import asyncio

import httpx
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Faculty

FACULTIES_URL = "https://schedule.ulbsibiu.ro/api/faculties"
TIMEOUT_SECONDS = 30.0


async def fetch_faculties(client: httpx.AsyncClient | None = None) -> object:
    """Return the decoded JSON body of GET /api/faculties.

    The response is `{"success", "message", "data": [...]}`; `_faculty_list` reads `data`.
    Raises httpx.HTTPStatusError on a non-2xx response.
    """
    if client is not None:
        return await _get_faculties(client)
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as own_client:
        return await _get_faculties(own_client)


async def _get_faculties(client: httpx.AsyncClient) -> object:
    response = await client.get(FACULTIES_URL)
    response.raise_for_status()
    return response.json()


def _faculty_list(payload: object) -> list:
    """Return the faculty list from a wrapped or raw payload."""
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    if isinstance(payload, list):
        return payload
    return []


def faculty_rows(payload: object) -> list[dict]:
    """Map the API faculties to `faculties` rows: the API `id` is our `code`."""
    return [{"code": f["id"], "name": f["name"]} for f in _faculty_list(payload)]


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


async def _main() -> None:
    payload = await fetch_faculties()
    with SessionLocal() as db:
        codes = upsert_faculties(db, payload)
    print("Faculties stored:", len(codes))
    print("Codes:", ", ".join(codes))


if __name__ == "__main__":
    asyncio.run(_main())
