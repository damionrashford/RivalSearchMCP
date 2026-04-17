"""
News aggregation tools for FastMCP server.
Aggregates news from free sources without authentication.
"""

from typing import Literal

from fastmcp import FastMCP

from src.core.news import NewsAggregator
from src.core.quality import assess_results, summarize_quality
from src.logging.logger import logger
from src.utils.markdown_formatter import format_news_markdown


def register_news_tools(mcp: FastMCP):
    """Register news aggregation tools."""

    aggregator = NewsAggregator()

    @mcp.tool(
        annotations={
            "title": "News Aggregation",
            "readOnlyHint": True,
            "openWorldHint": True,
            "destructiveHint": False,
            "idempotentHint": False,
        },
        timeout=90.0,
    )
    async def news_aggregation(
        query: str,
        max_results: int = 10,
        language: str = "en",
        country: str = "US",
        time_range: Literal["anytime", "day", "week", "month"] = "anytime",
    ) -> str:
        """
        Aggregate news from multiple keyless sources concurrently.

        Sources queried in parallel (all verified working, no authentication
        required):
          - Google News RSS (search, with `when:` freshness operator)
          - Bing News RSS (search, with age filter; uses curl subprocess
            because Bing rejects httpx's TLS fingerprint)
          - The Guardian (full Content API via public "test" key)
          - GDELT 2.0 Doc API (global news index; may be rate-limited to
            one call per 5s per IP — gracefully skipped when throttled)
          - DuckDuckGo News (HTML scrape fallback)

        Results are deduplicated by URL and fuzzy title.

        Args:
            query: News search query
            max_results: Maximum unique results to return (default: 10)
            language: Language code (default: "en") — honored by Google News
            country: Country code (default: "US") — honored by Google News
            time_range: anytime | day | week | month (applied to every
                source that supports native freshness filtering; ignored by
                DuckDuckGo which has no freshness param)
        """
        try:
            logger.info("News aggregation: query=%r time_range=%s", query, time_range)
            articles = await aggregator.search_news(
                query=query,
                max_results=max_results,
                language=language,
                country=country,
                time_range=time_range,
            )
            # Annotate each article with a quality score + expose an
            # aggregate confidence summary. Rule-based, cheap, deterministic.
            articles = assess_results(articles)
            confidence = summarize_quality(articles)
            return format_news_markdown(query, articles, time_range, confidence=confidence)

        except Exception as e:
            logger.error(f"News aggregation failed: {e}")
            return f"# 📰 News Search Results\n\n❌ **Error:** {str(e)}"
