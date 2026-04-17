"""
Traversal tools for FastMCP server.
Handles website research, documentation exploration, and website mapping.
"""

from typing import Literal, Optional

from fastmcp import Context, FastMCP

from src.core.traverse import (
    explore_documentation,
    map_website_structure,
    research_topic,
)
from src.logging.logger import logger
from src.utils import clean_html_to_markdown
from src.utils.markdown_formatter import format_traversal_markdown


def register_traversal_tools(mcp: FastMCP):
    """Register all traversal-related tools."""

    @mcp.tool(
        annotations={
            "title": "Map Website",
            "readOnlyHint": True,
            "openWorldHint": True,
            "destructiveHint": False,
            "idempotentHint": False,
        },
        timeout=90.0,
    )
    async def map_website(
        url: str,
        mode: Literal["research", "docs", "map"] = "research",
        max_pages: int = 5,
        max_depth: int = 2,
        generate_llms_txt: bool = False,
        ctx: Optional[Context] = None,
    ) -> str:
        """
        Map and explore websites with different modes for different use cases.

        Args:
            url: Website URL to traverse
            mode: Traversal mode - "research" (general), "docs" (documentation), "map" (structure)
            max_pages: Maximum number of pages to traverse
            max_depth: Maximum depth for mapping mode
        """

        async def _progress(p: float, t: float, msg: str) -> None:
            if ctx is None:
                return
            try:
                await ctx.report_progress(progress=p, total=t, message=msg)
            except Exception:
                pass

        try:
            logger.info(f"Traversing website: {url} in {mode} mode")
            await _progress(5, 100, f"starting {mode} traversal of {url}")

            if mode == "research":
                result = await research_topic(url, max_pages=max_pages)
            elif mode == "docs":
                result = await explore_documentation(url, max_pages=max_pages)
            elif mode == "map":
                result = await map_website_structure(url, max_pages=max_pages)
            else:
                return format_traversal_markdown(
                    {
                        "success": False,
                        "pages": [],
                        "summary": f"Invalid mode: {mode}. Use 'research', 'docs', or 'map'",
                        "total_pages": 0,
                        "source": url,
                    }
                )

            await _progress(60, 100, f"fetched {len(result)} pages, cleaning content")

            # Convert result to simple dict format with clean content
            pages = []
            total_pages = len(result)
            for i, page_dict in enumerate(result, 1):
                # Clean HTML content
                raw_content = page_dict.get("content", "")
                clean_content = clean_html_to_markdown(str(raw_content), page_dict.get("url", ""))

                pages.append(
                    {
                        "url": page_dict.get("url", ""),
                        "title": page_dict.get("title", ""),
                        "content": clean_content,
                        "depth": page_dict.get("depth", 0),
                    }
                )
                # Map page-cleaning into the 60-85% range.
                if total_pages:
                    await _progress(
                        60 + (25 * i / total_pages),
                        100,
                        f"cleaned {i}/{total_pages}",
                    )

            response = {
                "success": True,
                "pages": pages,
                "summary": f"Successfully traversed {len(result)} pages in {mode} mode",
                "total_pages": len(result),
                "source": url,
                "mode": mode,
            }

            if generate_llms_txt:
                # Generate LLMs.txt content
                llms_txt_content = f"""# {url}

This file contains information about {url} for Large Language Models.

## Site Information
- URL: {url}
- Traversal Mode: {mode}
- Pages Traversed: {len(pages)}

## Content Summary
{response["summary"]}

## Key Pages
"""
                for page in pages[:10]:  # Include up to 10 key pages
                    llms_txt_content += f"- {page['title']}: {page['url']}\n"

                response["llms_txt"] = llms_txt_content

            # Auto-attach quality scores + aggregate confidence per page.
            await _progress(90, 100, "scoring results")
            try:
                from src.core.quality import assess_results, summarize_quality

                pages_scored = assess_results(response.get("pages") or [])
                response["pages"] = pages_scored
                if pages_scored:
                    response["confidence"] = summarize_quality(pages_scored)
            except Exception as e:
                logger.warning("map_website quality scoring failed: %s", e)

            await _progress(100, 100, "done")
            return format_traversal_markdown(response)

        except Exception as e:
            logger.error(f"Website traversal failed for {url}: {e}")
            return format_traversal_markdown(
                {
                    "success": False,
                    "pages": [],
                    "summary": f"Error: {str(e)}",
                    "total_pages": 0,
                    "source": url,
                    "mode": mode,
                }
            )
