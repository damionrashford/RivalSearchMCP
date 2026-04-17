"""
HTTP fetch helpers. Only the two functions below are used externally
(by src/tools/analysis.py). The previous wrapper-class hierarchy
(BaseFetcher/URLFetcher/BatchFetcher/EnhancedFetcher/UnifiedFetcher)
and the unused `rival_retrieve`/`google_search_fetch`/`cleanup_resources`
helpers have been removed as dead code.

For TLS-fingerprint-safe fetches use `src/utils/scrapling_client.py`
directly -- `base_fetch_url` already routes through it.
"""

from .base import base_fetch_url, stream_fetch

__all__ = ["base_fetch_url", "stream_fetch"]
