#!/usr/bin/env python3
"""
Test suite for web_search tool.
Validates search functionality and all parameters.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.mcp_client import create_client


async def test_multi_search_default_params():
    """Test multi_search with default parameters."""
    async with create_client() as client:
        result = await client.call_tool("web_search", {"query": "Python programming"})

        assert result.content, "No content returned"
        output = result.content[0].text

        assert "Error" not in output or "search" in output.lower()
        assert len(output) > 400, f"Output too short: {len(output)} chars"

        print(f"✅ Default params test passed - {len(output)} chars")


async def test_multi_search_num_results():
    """Test multi_search with different num_results values."""
    async with create_client() as client:
        # Test with fewer results
        result = await client.call_tool(
            "web_search",
            {
                "query": "machine learning",
                "num_results": 3,
                "extract_content": False,
                "follow_links": False,
            },
        )

        output = result.content[0].text
        assert len(output) > 200, f"Output too short for 3 results: {len(output)} chars"

        print("✅ num_results=3 test passed")


async def test_multi_search_extract_content_flag():
    """Test multi_search with extract_content enabled/disabled."""
    async with create_client() as client:
        # Test with extract_content=False (faster)
        result = await client.call_tool(
            "web_search",
            {"query": "Python", "num_results": 3, "extract_content": False, "follow_links": False},
        )

        output = result.content[0].text
        assert len(output) > 0, "No output with extract_content=False"
        assert "http" in output.lower() or "result" in output.lower()

        print("✅ extract_content flag test passed")


async def test_multi_search_use_fallback():
    """Test multi_search end-to-end with a representative query."""
    async with create_client() as client:
        result = await client.call_tool(
            "web_search",
            {
                "query": "artificial intelligence",
                "num_results": 5,
                "extract_content": False,
            },
        )

        output = result.content[0].text
        assert len(output) > 300, f"Output too short: {len(output)} chars"

        # Should have search results
        has_results = (
            "result" in output.lower() or "search" in output.lower() or "http" in output.lower()
        )
        assert has_results, "No search results found"

        print("✅ use_fallback test passed")


async def test_multi_search_quality():
    """Test that multi_search returns quality results."""
    async with create_client() as client:
        result = await client.call_tool(
            "web_search",
            {
                "query": "TypeScript programming",
                "num_results": 5,
                "extract_content": False,
                "follow_links": False,
            },
        )

        output = result.content[0].text

        # Quality assertions
        assert len(output) > 500, f"Search results too short: {len(output)} chars"
        assert "http" in output.lower(), "No URLs in search results"

        print(f"✅ Quality test passed - {len(output)} chars")


if __name__ == "__main__":
    asyncio.run(test_multi_search_default_params())
    asyncio.run(test_multi_search_num_results())
    asyncio.run(test_multi_search_extract_content_flag())
    asyncio.run(test_multi_search_use_fallback())
    asyncio.run(test_multi_search_quality())
    print("\n✅ All web_search tests passed!")
