import asyncio

import httpx
import pytest

from etl.downloader import FACULTIES_URL, _faculty_list, fetch_faculties

SAMPLE = {
    "success": True,
    "message": "ok",
    "data": [{"id": "dre", "name": "Facultatea de Drept"}],
}


def _fetch_with(handler):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_faculties(client)

    return asyncio.run(run())


def test_returns_decoded_body_on_200():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == FACULTIES_URL
        return httpx.Response(200, json=SAMPLE)

    payload = _fetch_with(handler)

    assert payload == SAMPLE
    assert _faculty_list(payload) == SAMPLE["data"]


def test_raises_on_server_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"success": False})

    with pytest.raises(httpx.HTTPStatusError):
        _fetch_with(handler)


def test_faculty_list_accepts_raw_list():
    raw = [{"id": "dre"}]
    assert _faculty_list(raw) == raw


def test_faculty_list_returns_empty_for_unknown_shape():
    assert _faculty_list({"unexpected": 1}) == []
