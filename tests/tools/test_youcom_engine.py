"""Unit tests for the opt-in You.com engine. HTTP is mocked; no network."""

import httpx
import pytest

from rival_search_mcp.core.search.engines.youcom import youcom_engine
from rival_search_mcp.core.search.engines.youcom.youcom_engine import (
    YoucomSearchEngine,
    YoucomSearchError,
    youcom_enabled,
)

WEB = [
    {
        "url": "https://example.com/a",
        "title": "A",
        "description": "desc a",
        "snippets": ["s1", "s2"],
        "page_age": "2026-10-01T00:00:00",
    },
    {"url": "", "title": "no url, skipped"},
    {"url": "https://example.com/b", "title": "B", "snippets": ["only snippet"]},
    {"url": "https://example.com/c", "title": "C", "description": "desc c"},
]


@pytest.fixture
def mock_http(monkeypatch):
    """Route the engine's httpx client through a MockTransport and record requests."""
    state = {"requests": [], "response": httpx.Response(200, json={"results": {"web": WEB}})}

    def handler(request):
        state["requests"].append(request)
        return state["response"]

    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(youcom_engine.httpx, "AsyncClient", client_factory)
    monkeypatch.delenv("YDC_API_KEY", raising=False)
    return state


async def test_keyless_request_and_parsing(mock_http):
    results = await YoucomSearchEngine().search("rival search", num_results=2)

    req = mock_http["requests"][0]
    assert req.method == "GET"
    assert str(req.url).startswith(youcom_engine.KEYLESS_URL)
    assert req.url.params["query"] == "rival search"
    assert req.url.params["count"] == "2"
    assert "x-api-key" not in req.headers
    assert req.headers["user-agent"] == "youdotcom-integration/damionrashford-rivalsearchmcp"

    assert [r.url for r in results] == ["https://example.com/a", "https://example.com/b"]
    assert [r.position for r in results] == [1, 2]
    assert results[0].engine == "You.com"
    assert results[0].description == "desc a"
    assert results[0].full_content == "s1\ns2"
    assert results[1].description == "only snippet"


async def test_keyed_request_uses_post_and_header(mock_http, monkeypatch):
    monkeypatch.setenv("YDC_API_KEY", "test-key")
    results = await YoucomSearchEngine().search("q", num_results=10)

    req = mock_http["requests"][0]
    assert req.method == "POST"
    assert str(req.url) == youcom_engine.KEYED_URL
    assert req.headers["x-api-key"] == "test-key"
    assert b'"count":10' in req.content.replace(b" ", b"")
    assert len(results) == 3


@pytest.mark.parametrize(
    "status,headers,needle",
    [
        (401, {}, "check YDC_API_KEY"),
        (403, {}, "check YDC_API_KEY"),
        (402, {}, "out of credits"),
        (429, {"Retry-After": "30"}, "retry after 30s"),
        (500, {}, "HTTP 500"),
    ],
)
async def test_http_errors_raise(mock_http, status, headers, needle):
    mock_http["response"] = httpx.Response(status, headers=headers, json={})
    with pytest.raises(YoucomSearchError, match=needle):
        await YoucomSearchEngine().search("q")


async def test_missing_web_array_raises(mock_http):
    mock_http["response"] = httpx.Response(200, json={"results": {}})
    with pytest.raises(YoucomSearchError):
        await YoucomSearchEngine().search("q")


def test_opt_in_flag(monkeypatch):
    monkeypatch.delenv("YDC_API_KEY", raising=False)
    monkeypatch.delenv("RIVAL_SEARCH_YOUCOM", raising=False)
    assert youcom_enabled() is False
    monkeypatch.setenv("RIVAL_SEARCH_YOUCOM", "1")
    assert youcom_enabled() is True
    monkeypatch.setenv("RIVAL_SEARCH_YOUCOM", "0")
    assert youcom_enabled() is False
    monkeypatch.setenv("YDC_API_KEY", "k")
    assert youcom_enabled() is True


def test_orchestrator_only_registers_when_opted_in(monkeypatch):
    from rival_search_mcp.tools.multi_search import MultiSearchOrchestrator

    monkeypatch.delenv("YDC_API_KEY", raising=False)
    monkeypatch.delenv("RIVAL_SEARCH_YOUCOM", raising=False)
    assert "youcom" not in MultiSearchOrchestrator().engines

    monkeypatch.setenv("RIVAL_SEARCH_YOUCOM", "1")
    orch = MultiSearchOrchestrator()
    assert "youcom" in orch.engines
    assert orch.engine_order[-1] == "youcom"
