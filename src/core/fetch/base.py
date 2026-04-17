#!/usr/bin/env python3
"""
Base fetching functionality for RivalSearchMCP.
Core URL fetching with optimized performance.
"""

from typing import Optional

from src.logging.logger import logger
from src.utils import get_http_client

# Performance configuration
STREAM_TIMEOUT = 30.0


async def base_fetch_url(url: str) -> Optional[str]:
    """
    Fetch raw HTML for a URL with caching.

    Delegates to src.utils.scrapling_client.fetch_html — one place in
    the codebase that knows how to survive Cloudflare / Akamai TLS
    fingerprinting so Wikipedia / Reddit / major publishers respond
    200 instead of 403. Falls back to plain httpx only if the
    Scrapling path fails.

    Returns:
        HTML content or None if every path failed.
    """
    from src.core.cache.cache_manager import get_cache_manager
    from src.utils.scrapling_client import fetch_html

    cache_manager = get_cache_manager()
    cache_key = f"url_content:{url}"

    try:
        cached_content = await cache_manager.get(cache_key)
        if cached_content:
            logger.debug(f"Using cached content for {url}")
            return cached_content
    except Exception as e:
        logger.debug(f"Cache read failed for {url}: {e}")

    content = await fetch_html(url, timeout=int(STREAM_TIMEOUT))
    if content:
        try:
            await cache_manager.set(cache_key, content, ttl_seconds=3600)
        except Exception:
            pass
        return content

    # httpx fallback: small set of endpoints prefer a plain client.
    try:
        client = await get_http_client()
        response = await client.get(url, timeout=STREAM_TIMEOUT)
        response.raise_for_status()
        content = response.text
        try:
            await cache_manager.set(cache_key, content, ttl_seconds=3600)
        except Exception:
            pass
        return content
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None


async def stream_fetch(
    url: str, chunk_size: int = 1024, timeout: float = STREAM_TIMEOUT
) -> Optional[str]:
    """
    Stream fetch content from a URL with timeout.

    Args:
        url: URL to fetch
        chunk_size: Size of chunks to read
        timeout: Request timeout

    Returns:
        Streamed content or None if failed
    """
    try:
        client = await get_http_client()
        async with client.stream("GET", url, timeout=timeout) as response:
            response.raise_for_status()

            content = []
            async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                content.append(chunk.decode("utf-8", errors="ignore"))

            return "".join(content)

    except Exception as e:
        logger.error(f"Stream fetch failed for {url}: {e}")
        return None
