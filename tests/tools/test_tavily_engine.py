"""
Tests for TavilySearchEngine and Tavily integration in MultiSearchOrchestrator.
Uses unittest.mock to avoid requiring a real Tavily API key.
"""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from src.core.search.engines.tavily.tavily_engine import TavilySearchEngine


@pytest.mark.asyncio
async def test_search_maps_results_to_multi_search_result():
    """Successful search maps Tavily results to MultiSearchResult correctly."""
    mock_response = {
        "results": [
            {
                "title": "Python Tutorial",
                "url": "https://example.com/python",
                "content": "Learn Python programming.",
                "raw_content": "Full article about Python programming.",
            },
            {
                "title": "Async Python",
                "url": "https://example.com/async",
                "content": "Async programming in Python.",
                "raw_content": None,
            },
        ]
    }

    with patch("src.core.search.engines.tavily.tavily_engine.AsyncTavilyClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value=mock_response)
        MockClient.return_value = mock_client

        engine = TavilySearchEngine(api_key="test-key")
        results = await engine.search("Python programming", num_results=5, extract_content=True)

    assert len(results) == 2

    assert results[0].title == "Python Tutorial"
    assert results[0].url == "https://example.com/python"
    assert results[0].description == "Learn Python programming."
    assert results[0].engine == "tavily"
    assert results[0].position == 1
    assert results[0].real_url == "https://example.com/python"
    assert results[0].full_content == "Full article about Python programming."

    assert results[1].title == "Async Python"
    assert results[1].position == 2
    assert results[1].full_content is None


@pytest.mark.asyncio
async def test_search_returns_empty_on_api_error():
    """search() returns [] on API error without raising."""
    with patch("src.core.search.engines.tavily.tavily_engine.AsyncTavilyClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(side_effect=Exception("API rate limit exceeded"))
        MockClient.return_value = mock_client

        engine = TavilySearchEngine(api_key="test-key")
        results = await engine.search("test query")

    assert results == []


@pytest.mark.asyncio
async def test_search_uses_basic_depth_when_extract_content_false():
    """search_depth is 'basic' when extract_content=False."""
    mock_response = {"results": []}

    with patch("src.core.search.engines.tavily.tavily_engine.AsyncTavilyClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value=mock_response)
        MockClient.return_value = mock_client

        engine = TavilySearchEngine(api_key="test-key")
        await engine.search("test", extract_content=False)

    mock_client.search.assert_called_once()
    call_kwargs = mock_client.search.call_args[1]
    assert call_kwargs["search_depth"] == "basic"


@pytest.mark.asyncio
async def test_search_uses_advanced_depth_when_extract_content_true():
    """search_depth is 'advanced' when extract_content=True."""
    mock_response = {"results": []}

    with patch("src.core.search.engines.tavily.tavily_engine.AsyncTavilyClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value=mock_response)
        MockClient.return_value = mock_client

        engine = TavilySearchEngine(api_key="test-key")
        await engine.search("test", extract_content=True)

    call_kwargs = mock_client.search.call_args[1]
    assert call_kwargs["search_depth"] == "advanced"


@pytest.mark.asyncio
async def test_close_calls_super_close():
    """close() properly cleans up the inherited httpx session."""
    with patch("src.core.search.engines.tavily.tavily_engine.AsyncTavilyClient") as MockClient:
        MockClient.return_value = AsyncMock()
        engine = TavilySearchEngine(api_key="test-key")

    # The engine inherits an httpx.AsyncClient as self.session from BaseSearchEngine
    engine.session = AsyncMock()
    engine.session.aclose = AsyncMock()

    await engine.close()

    engine.session.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_orchestrator_includes_tavily_when_key_set():
    """MultiSearchOrchestrator includes Tavily in engines when TAVILY_API_KEY is set."""
    with (
        patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test-key"}),
        patch("src.core.search.engines.tavily.tavily_engine.AsyncTavilyClient") as MockClient,
    ):
        MockClient.return_value = AsyncMock()

        from src.tools.multi_search import MultiSearchOrchestrator

        orchestrator = MultiSearchOrchestrator()

    assert "tavily" in orchestrator.engines
    assert "tavily" in orchestrator.engine_order


@pytest.mark.asyncio
async def test_orchestrator_skips_tavily_when_key_absent():
    """MultiSearchOrchestrator excludes Tavily when TAVILY_API_KEY is not set."""
    env = os.environ.copy()
    env.pop("TAVILY_API_KEY", None)

    with patch.dict(os.environ, env, clear=True):
        from src.tools.multi_search import MultiSearchOrchestrator

        orchestrator = MultiSearchOrchestrator()

    assert "tavily" not in orchestrator.engines
    assert "tavily" not in orchestrator.engine_order
