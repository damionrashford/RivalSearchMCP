"""
Social search tools for FastMCP server.

Searches Reddit, Hacker News, Dev.to, Product Hunt, Medium, Stack Overflow,
Bluesky, Lobste.rs, and Lemmy without authentication.
"""

import asyncio
from typing import List, Literal

from fastmcp import FastMCP

from src.core.social import (
    BlueskySearch,
    DevToSearch,
    HackerNewsSearch,
    LemmySearch,
    LobstersSearch,
    MediumSearch,
    ProductHuntSearch,
    RedditSearch,
    StackOverflowSearch,
)
from src.logging.logger import logger
from src.utils.markdown_formatter import format_social_media_markdown

Platform = Literal[
    "reddit",
    "hackernews",
    "devto",
    "producthunt",
    "medium",
    "stackoverflow",
    "bluesky",
    "lobsters",
    "lemmy",
]


def register_social_media_tools(mcp: FastMCP):
    """Register social search tools."""

    reddit_search = RedditSearch()
    hn_search = HackerNewsSearch()
    devto_search = DevToSearch()
    producthunt_search = ProductHuntSearch()
    medium_search = MediumSearch()
    stackoverflow_search = StackOverflowSearch()
    bluesky_search = BlueskySearch()
    lobsters_search = LobstersSearch()
    # Lemmy is instantiated per-call so callers can pick an instance.

    @mcp.tool(
        annotations={
            "title": "Social Search",
            "readOnlyHint": True,
            "openWorldHint": True,
            "destructiveHint": False,
            "idempotentHint": False,
        },
        timeout=90.0,
    )
    async def social_search(
        query: str,
        platforms: List[Platform] = [
            "reddit",
            "hackernews",
            "stackoverflow",
            "bluesky",
        ],
        max_results_per_platform: int = 10,
        max_results: int = 0,
        reddit_subreddit: str = "all",
        time_filter: str = "all",
        stackoverflow_site: str = "stackoverflow",
        lemmy_instance: str = "lemmy.world",
    ) -> str:
        """
        Search across social platforms and communities for discussions and content.

        Supported platforms (no authentication required):
          - reddit        Reddit (JSON API)
          - hackernews    Hacker News (Algolia-powered full-text search)
          - devto         Dev.to (tag lookup + recent-articles filter)
          - producthunt   Product Hunt (RSS feed + client-side filter)
          - medium        Medium (tag/topic RSS feeds + HTML fallback)
          - stackoverflow Stack Exchange (defaults to stackoverflow.com)
          - bluesky       Bluesky public posts (AT Protocol)
          - lobsters      Lobste.rs (HTML search + hot-feed fallback)
          - lemmy         Lemmy federated posts (default instance: lemmy.world)

        Args:
            query: Search query
            platforms: Platforms to query in parallel (see list above)
            max_results_per_platform: Max results per platform (default: 10)
            max_results: Alias overriding max_results_per_platform when > 0
            reddit_subreddit: Reddit subreddit ("all" for site-wide)
            time_filter: Reddit time filter (all, day, week, month, year)
            stackoverflow_site: Stack Exchange site id (stackoverflow,
                serverfault, askubuntu, superuser, etc.)
            lemmy_instance: Lemmy instance to query against (default lemmy.world)
        """
        try:
            limit = max_results if max_results > 0 else max_results_per_platform
            logger.info(f"Social search for: {query} on {platforms}")

            tasks = {}
            if "reddit" in platforms:
                tasks["reddit"] = reddit_search.search(
                    query=query,
                    subreddit=reddit_subreddit,
                    limit=limit,
                    time_filter=time_filter,
                )
            if "hackernews" in platforms:
                tasks["hackernews"] = hn_search.search(query=query, limit=limit)
            if "devto" in platforms:
                tasks["devto"] = devto_search.search(query=query, per_page=limit)
            if "producthunt" in platforms:
                tasks["producthunt"] = producthunt_search.search(query=query, limit=limit)
            if "medium" in platforms:
                tasks["medium"] = medium_search.search(query=query, limit=limit)
            if "stackoverflow" in platforms:
                tasks["stackoverflow"] = stackoverflow_search.search(
                    query=query, site=stackoverflow_site, limit=limit
                )
            if "bluesky" in platforms:
                tasks["bluesky"] = bluesky_search.search(query=query, limit=limit)
            if "lobsters" in platforms:
                tasks["lobsters"] = lobsters_search.search(query=query, limit=limit)
            if "lemmy" in platforms:
                tasks["lemmy"] = LemmySearch(instance=lemmy_instance).search(
                    query=query, limit=limit
                )

            # Run all platform queries concurrently - each already handles
            # its own failures internally and returns [] on error, so
            # gathering them won't propagate a single failure.
            names = list(tasks.keys())
            outputs = await asyncio.gather(*tasks.values(), return_exceptions=True)

            # Auto-attach quality scores per platform + aggregate confidence
            try:
                from src.core.quality import assess_results, summarize_quality
            except Exception:
                assess_results = None
                summarize_quality = None

            results = {}
            union: List = []
            for name, output in zip(names, outputs):
                if isinstance(output, Exception):
                    logger.warning("Platform %s raised unexpectedly: %s", name, output)
                    items: List = []
                else:
                    items = output or []
                if assess_results and items:
                    items = assess_results(items)
                    union.extend(items)
                results[name] = {
                    "status": "success" if items else "no_results",
                    "count": len(items),
                    "results": items,
                }
            if summarize_quality and union:
                results["_confidence"] = summarize_quality(union)

            return format_social_media_markdown(query, results)

        except Exception as e:
            logger.error(f"Social search failed: {e}")
            return f"# 💬 Social Search Results\n\n❌ **Error:** {str(e)}"
