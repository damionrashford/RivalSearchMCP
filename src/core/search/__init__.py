#!/usr/bin/env python3
"""
Multi-engine web search package for RivalSearchMCP.

Callers import engines through `src.tools.multi_search.MultiSearchOrchestrator`
(the tool-layer entry point). The symbols re-exported here exist for tests
and for any caller that wants direct access to a single engine.
"""

from .core import BaseSearchEngine, MultiSearchResult
from .engines import DuckDuckGoSearchEngine, YahooSearchEngine

__all__ = [
    "BaseSearchEngine",
    "MultiSearchResult",
    "DuckDuckGoSearchEngine",
    "YahooSearchEngine",
]
