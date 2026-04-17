#!/usr/bin/env python3
"""
Test suite for social_search tool.
Validates Reddit, Hacker News, Dev.to, Product Hunt, and Medium search.
"""

import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.mcp_client import create_client


@pytest.mark.skipif(
    os.getenv("CI") == "true",
    reason="Reddit's Cloudflare layer blocks GitHub Actions IP ranges even with "
    "a compliant User-Agent. The source is resilient locally (see the "
    "old.reddit.com fallback in src/core/social/reddit.py) but there's no "
    "workaround for a static IP block. Covered by the local test runs.",
)
async def test_reddit_search():
    """Test Reddit search functionality."""
    async with create_client() as client:
        result = await client.call_tool(
            "social_search",
            {
                "query": "Python web frameworks",
                "platforms": ["reddit"],
                "max_results_per_platform": 5,
                "reddit_subreddit": "Python",
            },
        )

        output = result.content[0].text
        assert len(output) > 200, f"Reddit search output too short: {len(output)} chars"
        assert "reddit" in output.lower(), "No Reddit results found"

        print(f"✅ Reddit search test passed - {len(output)} chars")


async def test_hackernews_search():
    """Test Hacker News search functionality."""
    async with create_client() as client:
        result = await client.call_tool(
            "social_search",
            {"query": "TypeScript", "platforms": ["hackernews"], "max_results_per_platform": 5},
        )

        output = result.content[0].text
        assert len(output) > 200, f"Hacker News search output too short: {len(output)} chars"
        assert "hacker" in output.lower() or "news" in output.lower()

        print(f"✅ Hacker News search test passed - {len(output)} chars")


async def test_devto_search():
    """Test Dev.to search functionality."""
    async with create_client() as client:
        result = await client.call_tool(
            "social_search",
            {"query": "React", "platforms": ["devto"], "max_results_per_platform": 5},
        )

        output = result.content[0].text
        assert len(output) > 100, f"Dev.to search output too short: {len(output)} chars"

        print(f"✅ Dev.to search test passed - {len(output)} chars")


async def test_all_platforms():
    """Test searching all platforms simultaneously."""
    async with create_client() as client:
        result = await client.call_tool(
            "social_search",
            {
                "query": "JavaScript",
                "platforms": ["reddit", "hackernews", "devto"],
                "max_results_per_platform": 3,
            },
        )

        output = result.content[0].text
        assert len(output) > 300, f"Multi-platform search too short: {len(output)} chars"

        print(f"✅ All platforms test passed - {len(output)} chars")


async def test_time_filter():
    """Test Reddit time filter parameter."""
    async with create_client() as client:
        result = await client.call_tool(
            "social_search",
            {
                "query": "Python",
                "platforms": ["reddit"],
                "time_filter": "week",
                "max_results_per_platform": 5,
            },
        )

        output = result.content[0].text
        assert len(output) > 100, "Time filter test output too short"

        print("✅ Time filter test passed")


if __name__ == "__main__":
    asyncio.run(test_reddit_search())
    asyncio.run(test_hackernews_search())
    asyncio.run(test_devto_search())
    asyncio.run(test_all_platforms())
    asyncio.run(test_time_filter())
    print("\n✅ All social_search tests passed!")
