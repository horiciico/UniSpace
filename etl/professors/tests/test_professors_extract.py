"""Professors extract: pagination, normalization, skip rules and files, with a mock transport (no network)."""
import asyncio
import json

import httpx

from etl.professors.extract import (
    PER_PAGE,
    PROFESSORS_URL,
    extract_faculties,
    fetch_faculty_pages,
    normalize,
)

UUID_A = "3601532c-3e19-4edf-a41f-d1b996f6487b"
UUID_B = "99cc2327-bf8e-439a-8d33-c0f9bb2ddb37"


def person(id=UUID_A, name="Popescu Ana", email="Ana.Popescu@ulbsibiu.ro", **extra) -> dict:
    return {"id": id, "name": name, "email": email, "academicDegree": "Conf.",
            "employmentType": "full", "allDepartments": [], **extra}


def body(items: list, last: int) -> dict:
    return {"success": True, "message": "ok", "data": items,
            "pagination": {"current_page": 1, "last_page": last, "per_page": PER_PAGE}}


def paged(pages: dict[int, dict], seen: list) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=pages[int(request.url.params["page"])])
    return httpx.MockTransport(handler)


def client_for(transport: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=transport)


def test_every_page_is_fetched_in_order_with_the_query_parameters() -> None:
    seen: list[httpx.Request] = []
    pages = {1: body([person(UUID_A)], 3), 2: body([person(UUID_B)], 3), 3: body([], 3)}

    async def run():
        async with client_for(paged(pages, seen)) as client:
            return await fetch_faculty_pages(client, "ing")

    items = asyncio.run(run())

    assert [p["id"] for p in items] == [UUID_A, UUID_B]
    assert [int(r.url.params["page"]) for r in seen] == [1, 2, 3]
    first = seen[0]
    assert first.url.path == "/api/faculties/ing/professors"
    assert first.url.params["per_page"] == "500"
    assert first.url.params["with_exams_only"] == "false"
    assert PROFESSORS_URL.format(code="ing").endswith("/api/faculties/ing/professors")


def test_a_single_page_is_fetched_once() -> None:
    seen: list[httpx.Request] = []

    async def run():
        async with client_for(paged({1: body([person()], 1)}, seen)) as client:
            return await fetch_faculty_pages(client, "sti")

    assert len(asyncio.run(run())) == 1
    assert len(seen) == 1


def test_email_is_stripped_and_lower_cased() -> None:
    record, reason = normalize(person(email="  Ana.Popescu@ULBSibiu.ro \n"))
    assert reason is None
    assert record == {"id": UUID_A, "name": "Popescu Ana", "email": "ana.popescu@ulbsibiu.ro"}


def test_only_id_name_and_email_are_kept() -> None:
    record, _ = normalize(person(academicDegree="Prof.", departments=["x"]))
    assert set(record) == {"id", "name", "email"}


def test_null_empty_and_blank_emails_are_skipped() -> None:
    for email in (None, "", "   ", "\t\n"):
        assert normalize(person(email=email)) == (None, "no email")
    assert normalize(person(email=42)) == (None, "no email")


def test_unreadable_id_and_missing_name_are_skipped() -> None:
    assert normalize(person(id="not-a-uuid")) == (None, "id is not a UUID")
    assert normalize(person(id=None)) == (None, "id is not a UUID")
    assert normalize(person(name=None)) == (None, "no name")
    assert normalize(person(name="   ")) == (None, "no name")


def test_name_is_stripped() -> None:
    record, _ = normalize(person(name="  Popescu Ana "))
    assert record["name"] == "Popescu Ana"


def test_http_error_is_reported_and_other_faculties_still_run(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "/faculties/bad/" in request.url.path:
            return httpx.Response(500)
        return httpx.Response(200, json=body([person()], 1))

    results = asyncio.run(extract_faculties(["bad", "ing"], tmp_path, transport=httpx.MockTransport(handler)))

    assert [(r.code, r.status) for r in results] == [("bad", "error"), ("ing", "ok")]
    assert "500" in results[0].note
    assert not (tmp_path / "bad.json").exists()
    assert (tmp_path / "ing.json").exists()


def test_the_file_holds_the_normalized_records_and_the_skips(tmp_path) -> None:
    items = [person(UUID_A), person(UUID_B, email=None), person(id="x", name="Bad Id")]
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=body(items, 1)))

    results = asyncio.run(extract_faculties(["ing"], tmp_path, transport=transport))

    assert results[0].status == "ok"
    assert results[0].stored == 1
    assert results[0].skipped == 2
    document = json.loads((tmp_path / "ing.json").read_text(encoding="utf-8"))
    assert document["faculty_code"] == "ing"
    assert document["professors"] == [{"id": UUID_A, "name": "Popescu Ana", "email": "ana.popescu@ulbsibiu.ro"}]
    assert document["skipped"] == [
        {"id": UUID_B, "reason": "no email"},
        {"id": "x", "reason": "id is not a UUID"},
    ]
    assert "fetched_at" in document
