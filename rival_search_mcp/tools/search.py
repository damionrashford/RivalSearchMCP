"""
Search tools for FastMCP server.
Registers web_search across DuckDuckGo, Google (SerpBase), Bing, Yahoo, Mojeek, and Wikipedia.
"""

from typing import Annotated

from fastmcp import Context, FastMCP
from pydantic import Field

from rival_search_mcp.tools.multi_search import web_search


def register_search_tools(mcp: FastMCP):
    """Register all search-related tools."""

    # Google search is now supported via SerpBase API engine.
    # Set SERPBASE_API_KEY env var to enable it.

    @mcp.tool(
        name="web_search",
        description=(
            "Concurrent multi-engine web search across DuckDuckGo, Google (SerpBase), Bing, "
            "Yahoo, Mojeek, and Wikipedia. Results are deduplicated and "
            "merged; failures on any single engine do not block the others. "
            "Google results require SERPBASE_API_KEY environment variable."
        ),
        tags={
            "search",
            "web",
            "duckduckgo",
            "google",
            "bing",
            "yahoo",
            "mojeek",
            "wikipedia",
        },
        meta={
            "version": "2.1",
            "category": "Search",
            "engines": ["duckduckgo", "google", "bing", "yahoo", "mojeek", "wikipedia"],
        },
        annotations={
            "title": "Web Search",
            "readOnlyHint": True,
            "openWorldHint": True,
            "destructiveHint": False,
            "idempotentHint": False,
        },
        # 6 engines concurrent + optional per-result content fetch.
        timeout=90.0,
    )
    async def web_search_tool(
        ctx: Context,
        query: Annotated[
            str, Field(description="Search query string", min_length=2, max_length=500)
        ],
        num_results: Annotated[
            int,
            Field(description="Number of results per engine", ge=1, le=20, default=10),
        ] = 10,
        extract_content: Annotated[
            bool,
            Field(description="Whether to extract full page content", default=True),
        ] = True,
        follow_links: Annotated[
            bool, Field(description="Whether to follow internal links", default=True)
        ] = True,
        max_depth: Annotated[
            int,
            Field(description="Maximum depth for link following", ge=1, le=3, default=2),
        ] = 2,
    ) -> str:
        """
        Multi-engine search across DuckDuckGo, Google (SerpBase), Bing, Yahoo,
        Mojeek, and Wikipedia with input sanitization and rate-limit protection.
        """
        from rival_search_mcp.core.security.security import InputValidator

        validator = InputValidator()
        valid_query, cleaned_query = validator.validate_search_query(query)
        if not valid_query:
            await ctx.error(f"Query validation failed: {cleaned_query}")
            return f"❌ **Error:** Invalid query: {cleaned_query}"

        return await web_search(
            query=cleaned_query,
            ctx=ctx,
            num_results=num_results,
            extract_content=extract_content,
            follow_links=follow_links,
            max_depth=max_depth,
        )
