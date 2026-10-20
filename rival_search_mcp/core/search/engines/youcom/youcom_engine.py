"""
You.com search engine implementation using the You.com Search API.

Opt-in. Off unless RIVAL_SEARCH_YOUCOM=1 or YDC_API_KEY is set.
Without a key it uses the keyless endpoint (100 searches/day per IP).
With YDC_API_KEY it uses the keyed endpoint.
"""

import os
from datetime import datetime
from typing import Any

import httpx

from rival_search_mcp.logging.logger import logger

from ...core.multi_engines import BaseSearchEngine, MultiSearchResult

KEYLESS_URL = "https://api.you.com/v1/agents/search"
KEYED_URL = "https://ydc-index.io/v1/search"
USER_AGENT = "youdotcom-integration/damionrashford-rivalsearchmcp"


def youcom_enabled() -> bool:
    """True when the user opted in, either explicitly or by setting a key."""
    flag = os.environ.get("RIVAL_SEARCH_YOUCOM", "").strip().lower()
    return flag in {"1", "true", "yes", "on"} or bool(os.environ.get("YDC_API_KEY", "").strip())


class YoucomSearchError(RuntimeError):
    """Raised on non-2xx responses so the orchestrator records a failed engine."""


class YoucomSearchEngine(BaseSearchEngine):
    """You.com web search over its JSON API (no HTML scraping)."""

    def __init__(self, api_key: str | None = None, timeout: float = 20.0):
        super().__init__("You.com", "https://you.com")
        self._api_key = api_key
        self.timeout = timeout

    @property
    def api_key(self) -> str:
        if self._api_key is not None:
            return self._api_key
        return os.environ.get("YDC_API_KEY", "").strip()

    async def search(
        self,
        query: str,
        num_results: int = 10,
        extract_content: bool = True,
        follow_links: bool = True,
        max_depth: int = 2,
    ) -> list[MultiSearchResult]:
        """Search You.com. Raises YoucomSearchError on HTTP errors."""
        logger.info(f"Starting You.com search for: {query}")
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        key = self.api_key

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            if key:
                headers["X-API-Key"] = key
                response = await client.post(
                    KEYED_URL, json={"query": query, "count": num_results}, headers=headers
                )
            else:
                response = await client.get(
                    KEYLESS_URL, params={"query": query, "count": num_results}, headers=headers
                )

        if response.status_code != 200:
            raise YoucomSearchError(self._describe_error(response, keyed=bool(key)))

        web = (response.json().get("results") or {}).get("web")
        if not isinstance(web, list):
            raise YoucomSearchError("You.com response had no results.web array")

        results = self._parse(web, num_results)
        logger.info(f"You.com search completed: {len(results)} results")
        return results

    def _parse(self, web: list[dict[str, Any]], num_results: int) -> list[MultiSearchResult]:
        now = datetime.now().isoformat()
        results: list[MultiSearchResult] = []
        for item in web:
            url = item.get("url") or ""
            if not url:
                continue
            snippets = [s for s in (item.get("snippets") or []) if s]
            description = self._clean_text(item.get("description") or " ".join(snippets))
            results.append(
                MultiSearchResult(
                    title=self._clean_text(item.get("title") or ""),
                    url=url,
                    description=description,
                    engine=self.name,
                    position=len(results) + 1,
                    timestamp=now,
                    full_content="\n".join(snippets) or None,
                )
            )
            if len(results) >= num_results:
                break
        return results

    @staticmethod
    def _describe_error(response: httpx.Response, keyed: bool) -> str:
        status = response.status_code
        if status in (401, 403):
            return f"You.com rejected the request ({status}): check YDC_API_KEY"
        if status == 402:
            return "You.com returned 402: the API key is out of credits"
        if status == 429:
            retry = response.headers.get("Retry-After")
            limit = "rate limit" if keyed else "keyless limit (100 searches/day per IP)"
            hint = f", retry after {retry}s" if retry else ""
            return f"You.com {limit} reached (429){hint}; set YDC_API_KEY for more"
        return f"You.com returned HTTP {status}"
