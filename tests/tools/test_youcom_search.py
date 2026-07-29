#!/usr/bin/env python3
"""
Unit tests for the optional You.com search integration.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rival_search_mcp.core.search.engines.youcom.youcom_engine import YouComSearchEngine
from rival_search_mcp.tools.multi_search import MultiSearchOrchestrator


def test_youcom_parser_maps_common_result_shapes():
    engine = YouComSearchEngine(api_key="test-key")
    payload = {
        "results": [
            {
                "title": "You.com result",
                "url": "https://example.com/you",
                "snippet": "A short summary",
            },
            {
                "name": "Nested result",
                "link": "https://example.com/nested",
                "description": "Nested summary",
            },
        ]
    }

    results = engine._parse_results(payload, limit=10)

    assert len(results) == 2
    assert results[0].engine == "You.com"
    assert results[0].title == "You.com result"
    assert results[0].url == "https://example.com/you"
    assert results[0].description == "A short summary"
    assert results[1].title == "Nested result"
    assert results[1].url == "https://example.com/nested"


async def test_youcom_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_YOUCOM_SEARCH", raising=False)

    orchestrator = MultiSearchOrchestrator()

    assert "youcom" not in orchestrator.engines
    await orchestrator.close_all_engines()


async def test_youcom_is_enabled_when_flagged(monkeypatch):
    monkeypatch.setenv("ENABLE_YOUCOM_SEARCH", "true")

    orchestrator = MultiSearchOrchestrator()

    assert "youcom" in orchestrator.engines
    assert isinstance(orchestrator.engines["youcom"], YouComSearchEngine)
    await orchestrator.close_all_engines()


if __name__ == "__main__":
    test_youcom_parser_maps_common_result_shapes()
    print("✅ You.com parser test passed")
