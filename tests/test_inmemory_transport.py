"""
FastMCP in-memory transport smoke tests.

Exercises the MCP protocol surface (initialize, tools/list, prompts/list,
resources/list) against the live server using FastMCP's in-memory Client.
No network, no subprocess, no HTTP — this is the cheapest possible proof
that the server still speaks MCP correctly after middleware / tool /
schema changes.

Kept deliberately shallow: we don't exercise every tool here (the
`tests/tools/` suite owns that). The goal is to catch protocol-level
regressions -- missing prompts, schema breakage, middleware crashes on
initialize, etc. -- in under a second.
"""

import pytest


@pytest.fixture
def app():
    """Import the real server app exactly once per test session."""
    from server import app as server_app

    return server_app


async def test_tools_list_matches_registered(app):
    """All 10 tools must be discoverable via the MCP protocol."""
    from fastmcp import Client

    async with Client(app) as client:
        tools = await client.list_tools()

    names = {t.name for t in tools}
    expected = {
        "web_search",
        "map_website",
        "content_operations",
        "research_topic",
        "scientific_research",
        "social_search",
        "news_aggregation",
        "github_search",
        "document_analysis",
        "research_memory",
    }
    assert names == expected, f"tool set drift: missing={expected - names} extra={names - expected}"


async def test_prompts_list(app):
    """All 4 prompts must be exposed via prompts/list."""
    from fastmcp import Client

    async with Client(app) as client:
        prompts = await client.list_prompts()

    names = {p.name for p in prompts}
    assert names == {
        "comprehensive_research",
        "multi_source_search",
        "deep_content_analysis",
        "academic_literature_review",
    }


async def test_prompt_get_returns_message_objects(app):
    """v3 requires typed Message objects; resolution must round-trip."""
    from fastmcp import Client

    async with Client(app) as client:
        result = await client.get_prompt(
            "comprehensive_research",
            {"topic": "pytest smoke", "depth": "basic"},
        )

    assert len(result.messages) == 1
    msg = result.messages[0]
    assert msg.role == "user"
    # v3 surfaces content as TextContent; .text is the payload.
    text = getattr(msg.content, "text", None) or str(msg.content)
    assert "pytest smoke" in text


async def test_tool_schemas_exclude_injected_ctx(app):
    """`ctx: Context` must be FastMCP-injected, never shown to clients."""
    from fastmcp import Client

    async with Client(app) as client:
        tools = await client.list_tools()

    for tool in tools:
        props = (tool.inputSchema or {}).get("properties", {}) or {}
        assert "ctx" not in props, f"{tool.name} leaks ctx into its schema"


async def test_research_memory_list_sessions(app):
    """research_memory is the lowest-side-effect tool — a list call proves
    dispatch + middleware + response rendering all work end-to-end."""
    from fastmcp import Client

    async with Client(app) as client:
        result = await client.call_tool(
            "research_memory",
            {"operation": "list"},
        )

    # The tool returns markdown; just prove we got a non-empty response
    # back through the full middleware stack without an error.
    text = result.content[0].text if result.content else ""
    assert isinstance(text, str)
    assert len(text) > 0
