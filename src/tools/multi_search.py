"""
Multi-search engine tool for RivalSearchMCP.
Provides comprehensive search across multiple engines with fallback support.
"""

import asyncio
import os
from datetime import datetime
from typing import Any, Dict

from fastmcp import Context

from src.core.search.engines.duckduckgo.duckduckgo_engine import DuckDuckGoSearchEngine
from src.core.search.engines.wikipedia.wikipedia_engine import WikipediaSearchEngine
from src.logging.logger import logger
from src.utils.markdown_formatter import format_multi_search_markdown


class MultiSearchOrchestrator:
    """Orchestrates searches across multiple engines with fallback support."""

    def __init__(self):
        self.engines = {
            "duckduckgo": DuckDuckGoSearchEngine(),
            "wikipedia": WikipediaSearchEngine(),
        }
        self.engine_order = ["duckduckgo", "wikipedia"]

        # Conditionally add Tavily engine when API key is available
        tavily_api_key = os.environ.get("TAVILY_API_KEY")
        if tavily_api_key:
            from src.core.search.engines.tavily.tavily_engine import TavilySearchEngine

            self.engines["tavily"] = TavilySearchEngine(api_key=tavily_api_key)
            self.engine_order.append("tavily")
            logger.info("Tavily search engine enabled")
        else:
            logger.debug("TAVILY_API_KEY not set; Tavily engine disabled")

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

    async def search_with_fallback(
        self,
        query: str,
        num_results: int = 10,
        extract_content: bool = True,
        follow_links: bool = True,
        max_depth: int = 2,
    ) -> Dict[str, Any]:
        """
        Deprecated - now just calls search_all_engines.
        Kept for backward compatibility.
        """
        return await self.search_all_engines(
            query=query,
            num_results=num_results,
            extract_content=extract_content,
            follow_links=follow_links,
            max_depth=max_depth,
        )

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


async def web_search(
    query: str,
    ctx: Context,
    num_results: int = 10,
    extract_content: bool = True,
    follow_links: bool = True,
    max_depth: int = 2,
    use_fallback: bool = True,
) -> str:
    """
    Web search across multiple engines with comprehensive content extraction and caching.

    Args:
        query: Search query to execute
        num_results: Number of results per engine (default: 10)
        extract_content: Whether to extract full page content (default: True)
        follow_links: Whether to follow internal links (default: True)
        max_depth: Maximum depth for link following (default: 2)
        use_fallback: Whether to use fallback strategy (default: True)
        ctx: FastMCP context for progress reporting

    Returns:
        Comprehensive search results from multiple engines
    """
    from src.core.cache.cache_manager import get_cache_manager

    try:
        await ctx.info(f"🔍 Starting multi-engine search for: {query}")
        await ctx.report_progress(0.1)

        # Create cache key based on search parameters
        cache_key = f"multi_search:{query}:{num_results}:{extract_content}:{follow_links}:{max_depth}:{use_fallback}"

        # Try to get cached result first
        cache_manager = get_cache_manager()
        cached_result = await cache_manager.get(cache_key)

        if cached_result:
            await ctx.info("✅ Using cached search results")
            await ctx.report_progress(1.0)
            return cached_result

        orchestrator = get_orchestrator()

        await ctx.report_progress(0.2)

        if use_fallback:
            results = await orchestrator.search_with_fallback(
                query=query,
                num_results=num_results,
                extract_content=extract_content,
                follow_links=follow_links,
                max_depth=max_depth,
            )
        else:
            results = await orchestrator.search_all_engines(
                query=query,
                num_results=num_results,
                extract_content=extract_content,
                follow_links=follow_links,
                max_depth=max_depth,
            )

        await ctx.report_progress(0.9)

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
