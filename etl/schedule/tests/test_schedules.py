"""Weekly schedule download, with a mock transport and a temporary folder (no network)."""
import asyncio
import json
from datetime import date

import httpx

from etl.schedule.downloader import (
    CurrentUnit,
    DownloadResult,
    _download_one,
    build_envelope,
    schedule_filename,
    write_json_atomic,
)

UNIT = CurrentUnit(
    faculty_code="sti",
    db_id="3f1c2a4e-0000-4000-8000-000000000001",
    external_id=12,
    name="Modul 1",
    type="module",
    start_date=date(2026, 9, 30),
    end_date=date(2026, 11, 30),
)
SCHEDULE = {"success": True, "message": "ok", "data": {"Luni": [{"id": 1, "subject": "Analiză"}]}}


def _run(handler, output_dir) -> DownloadResult:
    async def go():
        semaphore = asyncio.Semaphore(2)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await _download_one(client, semaphore, UNIT, output_dir, indent=2)

    return asyncio.run(go())


def test_filename_is_lower_case_with_underscores() -> None:
    assert schedule_filename("Modul 1", "sti") == "modul_1_sti.json"
    assert schedule_filename("Semestrul I", "ing") == "semestrul_i_ing.json"


def test_envelope_wraps_the_raw_schedule_with_unit_context() -> None:
    envelope = build_envelope(UNIT, SCHEDULE, "2026-11-19T18:00:00+00:00")
    assert envelope == {
        "faculty_code": "sti",
        "planning_time_unit": {
            "db_id": UNIT.db_id,
            "external_id": 12,
            "name": "Modul 1",
            "type": "module",
            "start_date": "2026-09-30",
            "end_date": "2026-11-30",
        },
        "fetched_at": "2026-11-19T18:00:00+00:00",
        "schedule": SCHEDULE,
    }


def test_success_writes_the_envelope_and_creates_the_folder(tmp_path) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json=SCHEDULE)

    output_dir = tmp_path / "data" / "schedules"  # does not exist yet
    result = _run(handler, output_dir)

    assert result.status == "ok"
    assert seen["url"] == (
        "https://schedule.ulbsibiu.ro/api/faculties/sti/schedule/weekly?planning_time_unit_id=12"
    )
    saved = json.loads((output_dir / "modul_1_sti.json").read_text(encoding="utf-8"))
    assert saved["faculty_code"] == "sti"
    assert saved["schedule"] == SCHEDULE
    assert result.size_kb and result.size_kb > 0
    assert not list(output_dir.glob("*.tmp"))


def test_http_error_is_reported_and_writes_nothing(tmp_path) -> None:
    result = _run(lambda request: httpx.Response(500, json={"success": False}), tmp_path)
    assert result.status == "error"
    assert "HTTP error" in result.note
    assert not (tmp_path / "modul_1_sti.json").exists()


def test_invalid_json_is_reported(tmp_path) -> None:
    result = _run(lambda request: httpx.Response(200, content=b"<html>not json</html>"), tmp_path)
    assert result.status == "error"
    assert "invalid JSON" in result.note


def test_timeout_is_reported(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timed out", request=request)

    result = _run(handler, tmp_path)
    assert result.status == "error"
    assert "timeout" in result.note


def test_write_is_atomic_and_returns_the_size(tmp_path) -> None:
    path = tmp_path / "x.json"
    size = write_json_atomic(path, {"a": "ă"}, indent=None)
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": "ă"}  # UTF-8, not escaped
    assert size == path.stat().st_size
    assert not (tmp_path / "x.json.tmp").exists()
