"""
Unit tests for the optional You.com search engine.
"""

import pytest

from rival_search_mcp.core.search.core.multi_engines import MultiSearchResult
from rival_search_mcp.core.search.engines.youcom.youcom_engine import YouComSearchEngine


class _FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class _FakeClient:
    last_request = None

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url, params=None, headers=None):
        _FakeClient.last_request = {
            "url": url,
            "params": params,
            "headers": headers,
        }
        return _FakeResponse(
            200,
            payload={
                "results": {
                    "web": [
                        {
                            "url": "https://example.com/agent",
                            "title": "Agent Search",
                            "description": "Search for agent tools",
                            "snippets": ["Snippet text"],
                            "contents": {"markdown": "# Agent Search"},
                        }
                    ],
                    "news": [
                        {
                            "url": "https://example.com/news",
                            "title": "Agent News",
                            "snippets": ["News snippet"],
                        }
                    ],
                }
            },
        )


@pytest.mark.asyncio
async def test_youcom_search_maps_results_and_sends_standard_headers(monkeypatch):
    monkeypatch.setattr(
        "rival_search_mcp.core.search.engines.youcom.youcom_engine.httpx.AsyncClient",
        _FakeClient,
    )

    engine = YouComSearchEngine(api_key="ydc-test-key")
    results = await engine.search(
        query="agent search",
        num_results=2,
        extract_content=False,
    )

    assert _FakeClient.last_request is not None
    assert _FakeClient.last_request["url"] == "https://ydc-index.io/v1/search"
    assert _FakeClient.last_request["params"] == {"query": "agent search", "count": 2}
    assert _FakeClient.last_request["headers"] == {
        "X-API-Key": "ydc-test-key",
        "User-Agent": "youdotcom-integration/damionrashford-rivalsearchmcp",
        "Accept": "application/json",
    }

    assert len(results) == 2
    first, second = results

    assert isinstance(first, MultiSearchResult)
    assert first.title == "Agent Search"
    assert first.url == "https://example.com/agent"
    assert first.description == "Search for agent tools"
    assert first.engine == "You.com"
    assert first.position == 1
    assert first.full_content == "# Agent Search"
    assert first.timestamp

    assert second.title == "Agent News"
    assert second.url == "https://example.com/news"
    assert second.description == "News snippet"
    assert second.engine == "You.com"
    assert second.position == 2
    assert second.timestamp


def test_youcom_search_requires_api_key():
    with pytest.raises(ValueError, match="YDC_API_KEY"):
        YouComSearchEngine(api_key="   ")
