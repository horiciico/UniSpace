"""ETL downloader for the ULBS schedule API.

Step 1: fetch the faculties list and check its structure.
"""

import asyncio
import json

import httpx

FACULTIES_URL = "https://schedule.ulbsibiu.ro/api/faculties"
TIMEOUT_SECONDS = 30.0


async def fetch_faculties(client: httpx.AsyncClient | None = None) -> object:
    """Return the decoded JSON body of GET /api/faculties.

    The shape is not known yet (wrapped or raw list), so the raw JSON is returned.
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


async def _main() -> None:
    payload = await fetch_faculties()
    if isinstance(payload, dict):
        print("Top-level keys:", list(payload.keys()))
    else:
        print("Top-level type:", type(payload).__name__, "(raw list)")

    faculties = _faculty_list(payload)
    print("Number of faculties:", len(faculties))
    if faculties:
        print("First faculty:")
        print(json.dumps(faculties[0], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(_main())
