"""Professors extract: the error paths (a record that is not an object, invalid JSON, a file that cannot be written)."""
import asyncio
import json

import httpx

from etl.professors.extract import extract_faculties, normalize


def ok_body(items: list) -> dict:
    return {"success": True, "data": items, "pagination": {"last_page": 1}}


def test_a_record_that_is_not_an_object_is_skipped() -> None:
    assert normalize("text") == (None, "not an object")


def test_invalid_json_is_reported_for_that_faculty(tmp_path) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"<html>not json"))

    [result] = asyncio.run(extract_faculties(["ing"], tmp_path, transport=transport))

    assert result.status == "error"
    assert "invalid JSON" in result.note
    assert not (tmp_path / "ing.json").exists()


def test_a_file_that_cannot_be_written_is_reported(tmp_path) -> None:
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("x", encoding="utf-8")  # a file where the output folder should be
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=ok_body([])))

    [result] = asyncio.run(extract_faculties(["ing"], blocker, transport=transport))

    assert result.status == "error"
    assert "file error" in result.note


def test_a_skipped_record_that_is_not_an_object_keeps_no_id(tmp_path) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=ok_body(["junk"])))

    [result] = asyncio.run(extract_faculties(["ing"], tmp_path, transport=transport))

    assert result.skipped == 1
    document = json.loads((tmp_path / "ing.json").read_text(encoding="utf-8"))
    assert document["skipped"] == [{"id": None, "reason": "not an object"}]
