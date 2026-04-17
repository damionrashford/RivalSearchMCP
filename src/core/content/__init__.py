"""
Content extraction helpers. Only `UnifiedContentExtractor` is used outside
this package (by tools/analysis.py and search/multi_engines.py) -- the
earlier surface (parsers, cleaners, specialised extractors) has been
removed as dead code.
"""

from .extractors import UnifiedContentExtractor

__all__ = ["UnifiedContentExtractor"]
