"""Planning-unit selection and fetch order, with a mock transport (no network, no DB)."""
import asyncio
from datetime import date

import httpx

from etl.schedule.sync import fetch_active_planning_unit, pick_current

TODAY = date(2026, 11, 19)

MODUL_1 = {
    "id": 12, "year": 2026, "name": "Modul 1", "type": "module", "startDate": "2026-09-30",
    "endDate": "2026-11-30", "displayName": "Modul 1 2026", "isCurrent": True,
}
MODUL_2 = {
    "id": 13, "year": 2026, "name": "Modul 2", "type": "module", "startDate": "2026-12-02",
    "endDate": "2027-02-28", "displayName": "Modul 2 2026", "isCurrent": False,
}


def _client(responses: dict, seen: list) -> httpx.AsyncClient:
    """`responses` maps the `type` query value to the `data` list the API would return."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.url.params))
        return httpx.Response(200, json={"success": True, "data": responses[request.url.params["type"]]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _fetch(responses: dict, seen: list):
    async def run():
        async with _client(responses, seen) as client:
            return await fetch_active_planning_unit(client, "sti", 2026, today=TODAY)

    return asyncio.run(run())


def test_pick_current_prefers_the_flagged_unit() -> None:
    late = {"startDate": "2026-11-01", "endDate": "2026-12-31", "isCurrent": False}
    assert pick_current([late, MODUL_1], TODAY) is MODUL_1


def test_pick_current_falls_back_to_the_date_window() -> None:
    unflagged = {"startDate": "2026-11-01", "endDate": "2026-12-31", "isCurrent": False}
    assert pick_current([MODUL_2, unflagged], TODAY) is unflagged


def test_pick_current_returns_none_when_nothing_matches() -> None:
    assert pick_current([MODUL_2], TODAY) is None
    assert pick_current([], TODAY) is None


def test_semester_is_tried_first_and_module_used_when_it_is_empty() -> None:
    seen: list = []
    active = _fetch({"semester": [], "module": [MODUL_2, MODUL_1]}, seen)
    assert active.unit_type == "module"
    assert active.unit == MODUL_1
    assert [p["type"] for p in seen] == ["semester", "module"]


def test_module_is_used_when_semester_has_no_current_unit() -> None:
    seen: list = []
    semester_not_current = {"id": 3, "startDate": "2026-01-01", "endDate": "2026-02-01", "isCurrent": False}
    active = _fetch({"semester": [semester_not_current], "module": [MODUL_1]}, seen)
    assert active.unit_type == "module"
    assert active.unit == MODUL_1


def test_semester_wins_when_it_has_the_current_unit() -> None:
    seen: list = []
    semester = {"id": 1, "startDate": "2026-09-01", "endDate": "2027-01-31", "isCurrent": True}
    active = _fetch({"semester": [semester], "module": [MODUL_1]}, seen)
    assert active.unit_type == "semester"
    assert seen == [dict(year="2026", type="semester", active_only="false", visible_only="false")]


def test_returns_none_when_no_type_has_a_current_unit() -> None:
    seen: list = []
    assert _fetch({"semester": [], "module": [MODUL_2]}, seen) is None
    assert len(seen) == 2
