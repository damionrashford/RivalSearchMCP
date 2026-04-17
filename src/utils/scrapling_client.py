"""
Shared Scrapling-backed HTTP client for RivalSearchMCP.

Every tool that needs to fetch or parse external content routes
through here. The point of centralizing:

  1. One place that knows how to survive Cloudflare / Akamai TLS
     fingerprinting. Scrapling's AsyncFetcher drives tls_client
     with a real browser fingerprint + stealthy headers, so
     Wikipedia / Reddit / most major publishers respond 200 instead
     of 403.

  2. One parser with reliable text extraction. Scrapling's Selector
     handles malformed HTML better than BeautifulSoup's html.parser
     (which silently produces empty `.get_text()` output on some
     modern pages — Wikipedia being a notable example).

  3. Clean separation between "give me the HTML" and "give me the
     readable content" — search engines use `fetch_html` to scrape
     SERPs; research tools use `fetch_text` / `fetch_markdown` to
     pull article bodies.

Public API:

    fetch_page(url, *, timeout, impersonate)   -> Scrapling Page (low-level)
    fetch_html(url, **kwargs)                  -> raw HTML string or None
    fetch_text(url, **kwargs)                  -> extracted body text or None
    fetch_markdown(url, **kwargs)              -> markdown (via markdownify) or None

All returns None on non-200 / network failure; callers decide the
failure mode.
"""

from __future__ import annotations

from typing import Any, Optional

from src.logging.logger import logger

DEFAULT_TIMEOUT = 30


async def fetch_page(
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    impersonate: Optional[str] = None,
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
) -> Any:
    """Low-level fetch. Returns a Scrapling Page object or None on
    failure. Callers that need status / response headers / custom
    body handling use this directly."""
    try:
        from scrapling.fetchers import AsyncFetcher
    except ImportError as e:
        logger.error("scrapling not installed: %s", e)
        return None

    kwargs: dict = {"stealthy_headers": True, "timeout": timeout}
    if impersonate:
        kwargs["impersonate"] = impersonate
    if headers:
        kwargs["headers"] = headers
    if params:
        kwargs["params"] = params

    try:
        return await AsyncFetcher.get(url, **kwargs)
    except Exception as e:
        logger.warning("scrapling fetch failed for %s: %s", url, e)
        return None


async def fetch_html(url: str, **kwargs: Any) -> Optional[str]:
    """Return raw HTML body (str) or None on non-200 / failure."""
    page = await fetch_page(url, **kwargs)
    if page is None:
        return None
    if getattr(page, "status", None) != 200:
        logger.debug(
            "fetch_html non-200 for %s: status=%s",
            url,
            getattr(page, "status", None),
        )
        return None
    # Scrapling Page exposes .text (str) and .body (bytes).
    body_text = getattr(page, "text", None)
    if body_text:
        return body_text
    body_bytes = getattr(page, "body", None)
    if body_bytes:
        try:
            return body_bytes.decode("utf-8", "replace")
        except Exception:
            return None
    return None


async def fetch_text(url: str, **kwargs: Any) -> Optional[str]:
    """Return cleanly-extracted body text from the page, or None.

    Uses Scrapling's Selector (~1679× faster than BeautifulSoup
    html.parser) to walk the body. Prefers <main> when present,
    falls back to <body>, then the whole page.
    """
    page = await fetch_page(url, **kwargs)
    if page is None or getattr(page, "status", None) != 200:
        return None
    try:
        for selector in ("main", "article", "body"):
            nodes = page.css(selector)
            if nodes:
                text = nodes[0].get_all_text() or ""
                text = text.strip()
                if text:
                    return text
        # Final fallback: raw text
        raw = getattr(page, "text", None) or ""
        return raw.strip() or None
    except Exception as e:
        logger.warning("fetch_text extraction failed for %s: %s", url, e)
        return None


async def fetch_markdown(url: str, **kwargs: Any) -> Optional[str]:
    """Return markdown-formatted page content via markdownify, or
    None on failure / missing dependency.

    markdownify is a very small pure-Python dep that handles the
    HTML-to-markdown conversion reliably across pages where our
    BeautifulSoup+custom converter has historically produced empty
    output (Wikipedia article pages, for example).
    """
    html = await fetch_html(url, **kwargs)
    if not html:
        return None
    try:
        from markdownify import markdownify as md
    except ImportError:
        logger.warning("markdownify not installed; fetch_markdown falling back to fetch_text")
        # degrade gracefully
        return await fetch_text(url, **kwargs)
    try:
        return md(html, strip=["script", "style", "nav", "footer", "header"]).strip()
    except Exception as e:
        logger.warning("markdownify conversion failed for %s: %s", url, e)
        return None
