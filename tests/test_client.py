"""Проверка клиента YouTube Music на подставном сервере (httpx.MockTransport). Сеть не нужна."""
import asyncio
import json

import httpx
import pytest
from samples import CATALOG_TRACK, UGC_VIDEO, header, page

from app import client as client_module
from app.client import YouTubeMusicClient
from app.errors import UpstreamError


def page_html(key="KEY1", version="1.2026"):
    return f'<html>"INNERTUBE_API_KEY":"{key}","INNERTUBE_CONTEXT_CLIENT_VERSION":"{version}"</html>'


def make_client(handler):
    client = YouTubeMusicClient()
    client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), headers=client_module.HEADERS)
    return client


def run(coro):
    return asyncio.run(coro)


def test_three_pages_are_collected_and_config_is_downloaded_once():
    calls = {"pages": 0, "browse": []}

    def handler(request: httpx.Request):
        if request.method == "GET":
            calls["pages"] += 1
            return httpx.Response(200, text=page_html())
        body = json.loads(request.content)
        calls["browse"].append(body)
        assert request.url.params["key"] == "KEY1"
        assert body["context"]["client"]["clientVersion"] == "1.2026"
        if body.get("browseId") == "VLPLX":
            return httpx.Response(200, json=page([CATALOG_TRACK], token="T2", with_header=header("3 tracks")))
        if body.get("continuation") == "T2":
            return httpx.Response(200, json=page([UGC_VIDEO], token="T3"))
        if body.get("continuation") == "T3":
            return httpx.Response(200, json=page([CATALOG_TRACK]))
        return httpx.Response(500)

    client = make_client(handler)
    pages, truncated = run(client.fetch_playlist("PLX"))
    assert len(pages) == 3 and truncated is False
    assert [b.get("browseId") or b.get("continuation") for b in calls["browse"]] == ["VLPLX", "T2", "T3"]

    run(client.fetch_playlist("PLX"))  # второй вызов: страницу с ключом заново не скачиваем
    assert calls["pages"] == 1


def test_rejected_key_is_refreshed_once():
    state = {"downloads": 0}

    def handler(request: httpx.Request):
        if request.method == "GET":
            state["downloads"] += 1
            return httpx.Response(200, text=page_html(key=f"KEY{state['downloads']}"))
        if request.url.params["key"] == "KEY1":
            return httpx.Response(403)  # старый ключ отклонён
        return httpx.Response(200, json=page([CATALOG_TRACK], with_header=header("1 song")))

    pages, _ = run(make_client(handler).fetch_playlist("PLX"))
    assert len(pages) == 1 and state["downloads"] == 2


def test_key_rejected_twice_gives_upstream_error():
    def handler(request: httpx.Request):
        if request.method == "GET":
            return httpx.Response(200, text=page_html())
        return httpx.Response(403)

    with pytest.raises(UpstreamError) as error:
        run(make_client(handler).fetch_playlist("PLX"))
    assert error.value.status == 403


def test_rate_limit_keeps_retry_after():
    def handler(request: httpx.Request):
        if request.method == "GET":
            return httpx.Response(200, text=page_html())
        return httpx.Response(429, headers={"retry-after": "30"})

    with pytest.raises(UpstreamError) as error:
        run(make_client(handler).fetch_playlist("PLX"))
    assert error.value.status == 429 and error.value.retry_after == "30"


def test_page_without_key_gives_upstream_error():
    def handler(request: httpx.Request):
        return httpx.Response(200, text="<html>страница согласия на cookies</html>")

    with pytest.raises(UpstreamError):
        run(make_client(handler).fetch_playlist("PLX"))


def test_network_error_gives_upstream_error():
    def handler(request: httpx.Request):
        raise httpx.ConnectError("нет сети")

    with pytest.raises(UpstreamError):
        run(make_client(handler).fetch_playlist("PLX"))


def test_page_limit_marks_result_as_truncated(monkeypatch):
    monkeypatch.setattr(client_module, "MAX_PAGES", 2)

    def handler(request: httpx.Request):
        if request.method == "GET":
            return httpx.Response(200, text=page_html())
        return httpx.Response(200, json=page([CATALOG_TRACK], token="MORE"))  # токен есть всегда

    pages, truncated = run(make_client(handler).fetch_playlist("PLX"))
    assert len(pages) == 2 and truncated is True
