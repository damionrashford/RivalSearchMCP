"""
Multi-search engine tool for RivalSearchMCP.
Provides comprehensive search across multiple engines with fallback support.
"""

import asyncio
import os
from datetime import datetime
from typing import Any, Dict

from fastmcp import Context

from rival_search_mcp.core.search.engines.bing.bing_engine import BingSearchEngine
from rival_search_mcp.core.search.engines.duckduckgo.duckduckgo_engine import DuckDuckGoSearchEngine
from rival_search_mcp.core.search.engines.mojeek.mojeek_engine import MojeekSearchEngine
from rival_search_mcp.core.search.engines.wikipedia.wikipedia_engine import WikipediaSearchEngine
from rival_search_mcp.core.search.engines.yahoo.yahoo_engine import YahooSearchEngine
from rival_search_mcp.core.search.engines.youcom.youcom_engine import YouComSearchEngine
from rival_search_mcp.logging.logger import logger
from rival_search_mcp.utils.markdown_formatter import format_multi_search_markdown


class MultiSearchOrchestrator:
    """Orchestrates concurrent searches across the configured engines."""

    def __init__(self):
        self.engines = {
            "duckduckgo": DuckDuckGoSearchEngine(),
            "bing": BingSearchEngine(),
            "yahoo": YahooSearchEngine(),
            "mojeek": MojeekSearchEngine(),
            "wikipedia": WikipediaSearchEngine(),
        }
        if _env_flag("ENABLE_YOUCOM_SEARCH"):
            self.engines["youcom"] = YouComSearchEngine()
            logger.info("You.com search engine enabled via ENABLE_YOUCOM_SEARCH")
        self.engine_order = list(self.engines.keys())

    async def search_all_engines(
        self,
        query: str,
        num_results: int = 10,
        extract_content: bool = True,
        follow_links: bool = True,
        max_depth: int = 2,
    ) -> Dict[str, Any]:
        """
        Search across ALL engines concurrently with deduplication.

        All engines run simultaneously, results are combined and deduplicated by URL.

        Args:
            query: Search query
            num_results: Number of results per engine
            extract_content: Whether to extract full page content
            follow_links: Whether to follow internal links
            max_depth: Maximum depth for link following

        Returns:
            Dictionary with deduplicated results from all engines
        """
        logger.info(f"Starting concurrent search across {len(self.engines)} engines for: {query}")

        # Search all engines concurrently
        search_tasks = []
        for engine_name, engine in self.engines.items():
            task = engine.search(
                query=query,
                num_results=num_results,
                extract_content=extract_content,
                follow_links=follow_links,
                max_depth=max_depth,
            )
            search_tasks.append((engine_name, task))

        # Execute all searches in parallel
        search_results = await asyncio.gather(
            *[task for _, task in search_tasks], return_exceptions=True
        )

        # Process results from each engine
        results = {}
        all_results = []
        successful_engines = 0

        for i, (engine_name, _) in enumerate(search_tasks):
            engine_result = search_results[i]

            if isinstance(engine_result, Exception):
                logger.error(f"{engine_name} search failed: {engine_result}")
                results[engine_name] = {
                    "status": "failed",
                    "error": str(engine_result),
                    "count": 0,
                    "results": [],
                    "timestamp": datetime.now().isoformat(),
                }
            elif engine_result:
                results[engine_name] = {
                    "status": "success",
                    "count": len(engine_result),
                    "results": [result.to_dict() for result in engine_result],
                    "timestamp": datetime.now().isoformat(),
                }
                successful_engines += 1
                all_results.extend(engine_result)
                logger.info(f"{engine_name} search successful: {len(engine_result)} results")
            else:
                results[engine_name] = {
                    "status": "no_results",
                    "count": 0,
                    "results": [],
                    "timestamp": datetime.now().isoformat(),
                }

        # Deduplicate by URL
        seen_urls = set()
        deduplicated_results = []
        for result in all_results:
            url = result.url.lower().strip()
            if url not in seen_urls:
                seen_urls.add(url)
                deduplicated_results.append(result)

        logger.info(
            f"Deduplicated {len(all_results)} results to {len(deduplicated_results)} unique results"
        )

        # Generate summary
        summary = {
            "query": query,
            "engines_searched": len(self.engines),
            "successful_engines": successful_engines,
            "total_results": len(deduplicated_results),
            "results_before_dedup": len(all_results),
            "extract_content": extract_content,
            "follow_links": follow_links,
            "max_depth": max_depth,
            "timestamp": datetime.now().isoformat(),
        }

        # Add deduplicated results to the response
        results["deduplicated"] = {
            "status": "success",
            "count": len(deduplicated_results),
            "results": [result.to_dict() for result in deduplicated_results],
            "timestamp": datetime.now().isoformat(),
        }

        return {"summary": summary, "results": results}

    async def close_all_engines(self):
        """Close all engine sessions."""
        for engine in self.engines.values():
            try:
                await engine.close()
            except Exception as e:
                logger.debug(f"Error closing engine: {e}")


# Global orchestrator instance
_orchestrator = None


def get_orchestrator() -> MultiSearchOrchestrator:
    """Get or create the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MultiSearchOrchestrator()
    return _orchestrator


def _env_flag(name: str) -> bool:
    """Return True when the named environment variable is set to a truthy value."""
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


async def web_search(
    query: str,
    ctx: Context,
    num_results: int = 10,
    extract_content: bool = True,
    follow_links: bool = True,
    max_depth: int = 2,
) -> str:
    """
    Web search across multiple engines with comprehensive content extraction and caching.

    Args:
        query: Search query to execute
        num_results: Number of results per engine (default: 10)
        extract_content: Whether to extract full page content (default: True)
        follow_links: Whether to follow internal links (default: True)
        max_depth: Maximum depth for link following (default: 2)
        ctx: FastMCP context for progress reporting

    Returns:
        Comprehensive search results from multiple engines
    """
    from rival_search_mcp.core.cache.cache_manager import get_cache_manager

    try:
        await ctx.info(f"🔍 Starting multi-engine search for: {query}")
        await ctx.report_progress(0.1)

        cache_key = (
            f"multi_search:{query}:{num_results}:{extract_content}:{follow_links}:{max_depth}"
        )

        cache_manager = get_cache_manager()
        cached_result = await cache_manager.get(cache_key)

        if cached_result:
            await ctx.info("✅ Using cached search results")
            await ctx.report_progress(1.0)
            return cached_result

        orchestrator = get_orchestrator()

        await ctx.report_progress(0.2)

        results = await orchestrator.search_all_engines(
            query=query,
            num_results=num_results,
            extract_content=extract_content,
            follow_links=follow_links,
            max_depth=max_depth,
        )

        await ctx.report_progress(0.9)

        # Auto-attach quality scores to every result across every engine
        # so the downstream agent/reader gets a trust signal for free.
        try:
            from rival_search_mcp.core.quality import assess_results, summarize_quality

            union: list = []
            per_engine = results.get("results") or {}
            for engine_name, engine_data in per_engine.items():
                scored = assess_results(engine_data.get("results") or [])
                engine_data["results"] = scored
                union.extend(scored)
            if union:
                results.setdefault("summary", {})["confidence"] = summarize_quality(union)
        except Exception as e:
            logger.warning("web_search quality scoring failed: %s", e)

        # Format results
        formatted_results = format_multi_search_markdown(results)

        # Cache the formatted results (TTL: 30 minutes for search results)
        await cache_manager.set(cache_key, formatted_results, ttl_seconds=1800)

        # Count successful engines
        successful_engines = sum(
            1
            for engine_data in results.get("results", {}).values()
            if engine_data.get("status") == "success"
        )
        total_results = results.get("summary", {}).get("total_results", 0)

        await ctx.info(
            f"✅ Search completed: {total_results} total results from {successful_engines} engines"
        )
        await ctx.report_progress(1.0)

        return formatted_results

    except Exception as e:
        error_msg = f"Multi-engine search failed: {e}"
        logger.error(error_msg)
        await ctx.error(error_msg)

        return f"❌ **Error:** {error_msg}"
