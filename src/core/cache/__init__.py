"""
Cache backend. Callers use `get_cache_manager()` to obtain the lazily
created singleton; the underlying `CacheManager` class lives in
`cache_manager.py` and is the only implementation (the previous
wrapper that forwarded every method has been removed).
"""

from .cache_manager import get_cache_manager

__all__ = ["get_cache_manager"]
