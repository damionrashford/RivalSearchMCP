"""
You.com search engine implementation for RivalSearchMCP.

The adapter is opt-in so the default multi-engine fanout remains unchanged.
When enabled, it talks to the public You.com Search API and maps results into
the same MultiSearchResult shape used by the built-in engines.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from rival_search_mcp.logging.logger import logger

from ...core.multi_engines import BaseSearchEngine, MultiSearchResult


class YouComSearchEngine(BaseSearchEngine):
    """You.com Search API adapter."""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__("You.com", "https://api.you.com")
        self.search_url = "https://api.you.com/v1/agents/search"
        self.api_key = (api_key or os.getenv("YDC_API_KEY", "")).strip()
        self.user_agent = "youdotcom-integration/damionrashford-rivalsearchmcp"
        self._client: Optional[httpx.AsyncClient] = None

    async def search(
        self,
        query: str,
        num_results: int = 10,
        extract_content: bool = True,
        follow_links: bool = True,
        max_depth: int = 2,
    ) -> List[MultiSearchResult]:
        """Search You.com and optionally fetch result pages."""
        logger.info("Starting You.com search for: %s", query)

        payload = {
            "query": query,
            "count": max(1, min(num_results, 20)),
        }

        response = await self._post_json(payload)
        if response is None:
            return []

        results = self._parse_results(response, limit=num_results)
        logger.info("You.com returned %d results", len(results))

        if extract_content and results:
            for result in results:
                result.real_url = self._extract_real_url(result.url)
                target_url = result.real_url if result.real_url != result.url else result.url
                if not target_url:
                    continue

                content = await self._fetch_page_content(target_url)
                if not content:
                    continue

                result.full_content = self._extract_main_content(content)
                result.internal_links = self._extract_internal_links(content, target_url)

                if follow_links and result.internal_links and max_depth > 1:
                    result.second_level_content = await self._extract_second_level_content(
                        target_url, result.internal_links
                    )

        return results

    async def _post_json(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Call the You.com Search API and return decoded JSON."""
        client = await self._get_client()
        try:
            response = await client.post(self.search_url, json=payload)
        except Exception as exc:
            logger.warning("You.com fetch failed: %s", exc)
            return None

        if response.status_code != 200:
            logger.warning(
                "You.com returned %s for %r (body snippet: %s)",
                response.status_code,
                payload.get("query", ""),
                response.text[:200],
            )
            return None

        try:
            data = response.json()
        except Exception as exc:
            logger.warning("You.com returned invalid JSON: %s", exc)
            return None

        if not isinstance(data, dict):
            logger.warning("You.com response was not a JSON object")
            return None

        return data

    async def _get_client(self) -> httpx.AsyncClient:
        """Create a reusable client with the attribution header."""
        if self._client is None:
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self._client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers=headers,
            )

        return self._client

    def _parse_results(
        self, payload: Dict[str, Any], limit: int = 10
    ) -> List[MultiSearchResult]:
        """Map the API response into the shared search result shape."""
        items = self._find_items(payload)
        results: List[MultiSearchResult] = []

        for index, item in enumerate(items[:limit]):
            if not isinstance(item, dict):
                continue

            title = self._first_text(
                item,
                ["title", "name", "headline", "document_title", "result_title"],
            )
            url = self._first_text(
                item,
                ["url", "link", "href", "targetUrl", "target_url", "destination"],
            )
            description = self._first_text(
                item,
                ["description", "snippet", "summary", "text", "body", "excerpt"],
            )

            if not title and url:
                title = url
            if not title or not url:
                continue

            results.append(
                MultiSearchResult(
                    title=title,
                    url=url,
                    description=description,
                    engine=self.name,
                    position=index + 1,
                    timestamp=datetime.now().isoformat(),
                )
            )

        return results

    def _find_items(self, payload: Dict[str, Any]) -> List[Any]:
        """Find the first list of result objects in the response payload."""
        candidate_paths = [
            ("results",),
            ("hits",),
            ("items",),
            ("documents",),
            ("data", "results"),
            ("data", "hits"),
            ("data", "items"),
            ("response", "results"),
            ("response", "hits"),
            ("response", "items"),
        ]

        for path in candidate_paths:
            node: Any = payload
            for key in path:
                if not isinstance(node, dict):
                    node = None
                    break
                node = node.get(key)

            if isinstance(node, list):
                return node

            if isinstance(node, dict):
                for nested_key in ("results", "hits", "items", "documents"):
                    nested = node.get(nested_key)
                    if isinstance(nested, list):
                        return nested

        return []

    def _first_text(self, item: Dict[str, Any], keys: List[str]) -> str:
        """Return the first non-empty string value for the given keys."""
        for key in keys:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                for nested_key in ("text", "value", "content", "url"):
                    nested = value.get(nested_key)
                    if isinstance(nested, str) and nested.strip():
                        return nested.strip()
        return ""

    async def close(self):
        """Close the shared You.com HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
