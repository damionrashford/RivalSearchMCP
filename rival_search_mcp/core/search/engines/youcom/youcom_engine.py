"""
You.com search engine implementation for RivalSearchMCP.

You.com is opt-in through YDC_API_KEY so the default zero-key behavior
stays unchanged. The engine uses the direct Search API and mirrors the
shape of the existing engine adapters.
"""

from datetime import datetime
from typing import List

import httpx

from rival_search_mcp.logging.logger import logger

from ...core.multi_engines import BaseSearchEngine, MultiSearchResult

SEARCH_ENDPOINT = "https://ydc-index.io/v1/search"
DEFAULT_TIMEOUT = 30.0
USER_AGENT = "youdotcom-integration/damionrashford-rivalsearchmcp"


class YouComSearchEngine(BaseSearchEngine):
    """You.com search via the direct Search API."""

    def __init__(self, api_key: str):
        api_key = api_key.strip()
        if not api_key:
            raise ValueError("You.com search requires a non-empty YDC_API_KEY")

        super().__init__("You.com", "https://you.com")
        self.api_key = api_key

    async def search(
        self,
        query: str,
        num_results: int = 10,
        extract_content: bool = True,
        follow_links: bool = True,
        max_depth: int = 2,
    ) -> List[MultiSearchResult]:
        """Search You.com and return result cards in the common engine shape."""
        logger.info("Starting You.com search for: %s", query)

        results = await self._search_api(query, num_results)
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

    async def _search_api(self, query: str, num_results: int) -> List[MultiSearchResult]:
        """Query the You.com Search API and normalize the payload."""
        params = {
            "query": query,
            "count": min(max(1, num_results), 50),
        }

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.get(
                    SEARCH_ENDPOINT,
                    params=params,
                    headers={
                        "X-API-Key": self.api_key,
                        "User-Agent": USER_AGENT,
                        "Accept": "application/json",
                    },
                )
        except Exception as e:
            logger.error("You.com fetch failed: %s", e)
            return []

        if response.status_code != 200:
            logger.warning(
                "You.com returned %s for %r (body snippet: %s)",
                response.status_code,
                query,
                response.text[:200],
            )
            return []

        try:
            payload = response.json()
        except Exception as e:
            logger.error("You.com response parsing failed: %s", e)
            return []

        results: List[MultiSearchResult] = []
        items = list((payload.get("results") or {}).get("web") or [])
        items.extend((payload.get("results") or {}).get("news") or [])

        for i, item in enumerate(items[:num_results]):
            url = item.get("url", "")
            title = item.get("title") or url
            snippets = item.get("snippets") or []
            description = item.get("description") or (snippets[0] if snippets else "")
            markdown = (item.get("contents") or {}).get("markdown")

            if not url:
                continue

            results.append(
                MultiSearchResult(
                    title=title,
                    url=url,
                    description=description,
                    engine=self.name,
                    position=i + 1,
                    timestamp=datetime.now().isoformat(),
                    full_content=markdown,
                )
            )

        return results
