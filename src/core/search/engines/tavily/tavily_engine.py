"""
Tavily search engine implementation for RivalSearchMCP.
Uses the Tavily API for high-quality web search results.
Requires TAVILY_API_KEY environment variable to be set.
"""

from datetime import datetime
from typing import List

from tavily import AsyncTavilyClient

from src.logging.logger import logger

from ...core.multi_engines import BaseSearchEngine, MultiSearchResult


class TavilySearchEngine(BaseSearchEngine):
    """Tavily search engine implementation using the tavily-python SDK."""

    def __init__(self, api_key: str):
        super().__init__("Tavily", "https://api.tavily.com")
        self.client = AsyncTavilyClient(api_key=api_key)

    async def search(
        self,
        query: str,
        num_results: int = 10,
        extract_content: bool = True,
        follow_links: bool = True,
        max_depth: int = 2,
    ) -> List[MultiSearchResult]:
        """Search using the Tavily API and map results to MultiSearchResult."""
        try:
            logger.info(f"Starting Tavily search for: {query}")

            search_depth = "advanced" if extract_content else "basic"

            response = await self.client.search(
                query=query,
                max_results=min(num_results, 20),
                search_depth=search_depth,
                include_answer=False,
            )

            results: List[MultiSearchResult] = []
            tavily_results = response.get("results", [])

            for i, item in enumerate(tavily_results):
                result = MultiSearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    description=item.get("content", ""),
                    engine="tavily",
                    position=i + 1,
                    timestamp=datetime.now().isoformat(),
                    real_url=item.get("url", ""),
                    full_content=item.get("raw_content") if extract_content else None,
                )
                results.append(result)

            logger.info(f"Tavily search returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return []

    async def close(self):
        """Close the engine and inherited httpx session."""
        await super().close()
