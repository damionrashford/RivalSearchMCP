"""
Tests for optional You.com registration in the multi-search orchestrator.
"""

from rival_search_mcp.tools.multi_search import MultiSearchOrchestrator


def test_youcom_engine_is_disabled_without_env(monkeypatch):
    monkeypatch.delenv("YDC_API_KEY", raising=False)

    orchestrator = MultiSearchOrchestrator()

    assert "youcom" not in orchestrator.engines


def test_youcom_engine_is_enabled_with_env(monkeypatch):
    monkeypatch.setenv("YDC_API_KEY", "ydc-test-key")

    orchestrator = MultiSearchOrchestrator()

    assert "youcom" in orchestrator.engines
