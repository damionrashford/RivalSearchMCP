"""
SerpBase search engine — Google Search Results API.

SerpBase is a hosted API that returns structured Google search results
as JSON. Unlike the scraping-based engines (Bing, DuckDuckGo, Yahoo)
that parse HTML SERPs with Scrapling, this engine is purely API-driven:
a single HTTP GET, no selectors, no TLS fingerprinting required.

Requires SERPBASE_API_KEY environment variable.
See https://serpbase.dev/dashboard/api-keys to get a key.
"""

import os
from datetime import datetime
from typing import List

import httpx

from rival_search_mcp.logging.logger import logger

from ...core.multi_engines import BaseSearchEngine, MultiSearchResult


class SerpBaseSearchEngine(BaseSearchEngine):
    """Google search via SerpBase REST API — no scraping, just JSON."""

    API_URL = "https://api.serpbase.dev/google/search"

    def __init__(self):
        super().__init__("Google", "https://serpbase.dev")
        self.api_key = os.environ.get("SERPBASE_API_KEY", "")

    async def search(
        self,
        query: str,
        num_results: int = 10,
        extract_content: bool = True,
        follow_links: bool = True,
        max_depth: int = 2,
    ) -> List[MultiSearchResult]:
        """Search Google via SerpBase API.

        If SERPBASE_API_KEY is not set, logs a warning and returns
        an empty result list — other engines continue unaffected.
        """
        if not self.api_key:
            logger.warning(
                "SERPBASE_API_KEY not set — skipping SerpBase (Google) search. "
                "Get a key at https://serpbase.dev/dashboard/api-keys"
            )
            return []

        logger.info("Starting SerpBase (Google) search for: %s", query)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    self.API_URL,
                    params={
                        "q": query,
                        "num": min(num_results, 20),
                        "api_key": self.api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("SerpBase API error %s: %s", e.response.status_code, e.response.text[:200])
            return []
        except Exception as e:
            logger.error("SerpBase request failed: %s", e)
            return []

        results: List[MultiSearchResult] = []

        organic = data.get("organic_results", [])
        if not organic:
            logger.info("SerpBase returned 0 organic results for: %s", query)
            return results

        for item in organic[:num_results]:
            position = item.get("position", len(results) + 1)
            title = (item.get("title") or "").strip()
            link = (item.get("link") or "").strip()
            snippet = (item.get("snippet") or "").strip()

            if not title or not link:
                continue

            result = MultiSearchResult(
                title=title,
                url=link,
                description=snippet,
                engine=self.name,
                position=position,
                timestamp=datetime.now().isoformat(),
            )

            # Content extraction — same pattern as other engines
            if extract_content:
                result.real_url = link  # API links are direct, no redirect
                content = await self._fetch_page_content(link)
                if content:
                    result.full_content = self._extract_main_content(content)
                    result.internal_links = self._extract_internal_links(content, link)

                    if follow_links and result.internal_links and max_depth > 1:
                        result.second_level_content = await self._extract_second_level_content(
                            link, result.internal_links
                        )

            results.append(result)

        logger.info("SerpBase returned %d results", len(results))
        return results
