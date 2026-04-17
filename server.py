#!/usr/bin/env python3
"""
RivalSearchMCP Server - Advanced Web Research and Content Discovery
"""

import os

from fastmcp import FastMCP

# Import logger
from src.logging.logger import logger

# Import middleware
from src.middleware import register_middleware
from src.middleware.cors_validation import CORSOriginValidationMiddleware
from src.middleware.null_id_validation import NullIdValidationMiddleware

# Import prompts
from src.prompts import register_prompts

# Import custom routes
from src.routes.routes import register_custom_routes
from src.tools.analysis import register_analysis_tools
from src.tools.github_tool import register_github_tools
from src.tools.memory import register_memory_tools
from src.tools.news import register_news_tools
from src.tools.pdf_tool import register_pdf_tools

# Removed tools (capabilities folded into the tools above):
#   - research_agent   -> LLM-driven, replaced by deterministic tools
#   - entity_research  -> now research_topic(mode="entity")
#   - find_conflicts   -> now content_operations(operation="find_conflicts")
#   - score_sources    -> now content_operations(operation="score")
#   - 5 research_session_* tools -> now single research_memory(operation=...)
#   - trends_*         -> Google rate-limits, disabled
from src.tools.scientific import register_scientific_tools
from src.tools.search import register_search_tools
from src.tools.social_media import register_social_media_tools
from src.tools.traversal import register_traversal_tools

# Import modular tool registration functions


# Environment-based configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
PORT = int(os.getenv("PORT", "8000"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Comprehensive server instructions
SERVER_INSTRUCTIONS = """
Deterministic research and content-discovery MCP server. No LLM is run
inside the server itself — every tool returns structured, auditable
output that the caller's model (or a human) can reason over.

🎯 CORE PURPOSE:
Fan out across dozens of keyless data sources — web search, social
communities, news, GitHub, academic papers, datasets, PDFs — and
return results with per-item quality scores plus an aggregate
confidence signal so callers can calibrate trust rather than treating
all results as equal.

🛠️  AVAILABLE TOOLS (10):

Search (every result auto-annotated with a `quality` block + an
aggregate `confidence` summary — high / medium / low):
- web_search: DuckDuckGo + Bing + Yahoo + Mojeek + Wikipedia (no auth)
- social_search: Reddit, Hacker News, Dev.to, Product Hunt, Medium,
                 Stack Overflow, Bluesky, Lobste.rs, Lemmy (no auth)
- news_aggregation: Google News, Bing News, Guardian, GDELT, DuckDuckGo
                    News, with a `time_range` freshness filter (no auth)
- github_search: GitHub repositories via the public search API
- scientific_research: OpenAlex, CrossRef, arXiv, PubMed, Europe PMC for
                       papers; Kaggle, HuggingFace, Zenodo, Harvard
                       Dataverse for datasets (no auth)
- map_website: Structured website crawling (research / docs / map modes)

Content + Synthesis (operation-dispatched tools with Literal enums):
- content_operations: Pick `operation`:
    retrieve / stream / analyze / extract  (URL or content transforms)
    score                                  (rate a list of URLs)
    find_conflicts                         (numeric / date / polarity
                                            disagreements across URLs)
- research_topic: Pick `mode`:
    topic    (open-ended search + fetch + extract)
    entity   (unified cross-source profile of a named entity, fanning
              out across web + news + github + social + academic)
  Accepts `session_id` to auto-save findings to research memory.
- document_analysis: PDF, DOCX, text, images (OCR) — up to 50MB.

Memory (one tool, `operation` enum covers all CRUD):
- research_memory: Pick `operation`:
    start  → create a workspace, returns session_id
    add    → append findings and/or a note
    get    → read full workspace state
    list   → enumerate workspaces (optional tag filter)
    delete → remove a workspace

📋 USAGE PATTERNS:

1. Quick search: web_search → content_operations(operation="retrieve")
   → document_analysis for PDFs
2. Entity profile: research_topic(mode="entity", topic=...) — one call
   fans out across every source and returns a unified report
3. Trust check: content_operations(operation="score", urls=[...])
4. Conflict check: content_operations(operation="find_conflicts",
   urls=[...], claim?=...)
5. Iterative research: research_memory(operation="start", topic=...)
   → pass session_id into research_topic or research_memory(add)
   across calls to accumulate findings
6. Academic: scientific_research(operation="academic_search") →
   document_analysis on PDF links

💡 BEST PRACTICES:
- Every search tool attaches `quality` per result — weight findings by
  it when synthesizing; treat `confidence="low"` as a cue to cross-check
- Combine tools: search → score → retrieve → analyze → conflicts
- For multi-step research, use research_memory to carry context forward

🚀 PERFORMANCE:
- Multi-source tools fan out concurrently (asyncio.gather)
- Per-source failures are isolated; other sources still populate output
- Scrapling-backed search engines resist Cloudflare TLS fingerprinting
- GitHub rate limiting: 60 requests/hour unauthenticated

📊 MONITORING:
- Health: /health
- Metrics: /metrics
- Status: /status
- Tools: /tools
"""

# Create enhanced FastMCP server instance. In v3 the per-component
# `on_duplicate_*` kwargs are collapsed into a single `on_duplicate`
# and `include_fastmcp_meta` is gone (metadata is always included).
#
# mask_error_details=True: generic exceptions surface to clients as
# "Tool execution failed" instead of leaking internal paths / parser
# state / httpx URLs. User-facing validation errors must explicitly
# raise fastmcp.exceptions.ToolError to pass through the mask.
app = FastMCP(
    name="RivalSearchMCP",
    instructions=SERVER_INSTRUCTIONS,
    on_duplicate="error",
    mask_error_details=True,
)

# Register middleware for production readiness
register_middleware(app)

# Register all tools using modular approach

register_search_tools(app)  # web_search
register_traversal_tools(app)  # map_website
register_analysis_tools(app)  # content_operations + research_topic
register_scientific_tools(app)  # scientific_research
register_social_media_tools(app)  # social_search
register_news_tools(app)  # news_aggregation
register_github_tools(app)  # github_search
register_pdf_tools(app)  # document_analysis
register_memory_tools(app)  # research_memory (single tool, 5 ops)

# Register prompts
register_prompts(app)

# Register custom routes
register_custom_routes(app)

# Start background tasks that require event loop
from src.middleware.middleware import start_background_tasks  # noqa: E402

start_background_tasks()


def _wrap_http_app_with_security_middleware():
    """Ensure HTTP-level security middleware is applied for all deployments.

    FastMCP Cloud/Horizon calls app.http_app() directly (ignores __main__),
    so we wrap it to always include our HTTP-level validation middleware.

    Middleware order (outermost → innermost):
      1. CORSOriginValidationMiddleware  – blocks untrusted origins (MUST per spec)
      2. NullIdValidationMiddleware       – rejects id: null requests
      3. … FastMCP / Starlette internals
    """
    from starlette.middleware import Middleware

    _original_http_app = app.http_app

    def _http_app(**kwargs):
        middleware = list(kwargs.pop("middleware", None) or [])
        # Insert in reverse order so the first entry runs outermost
        middleware.insert(0, Middleware(NullIdValidationMiddleware))
        middleware.insert(0, Middleware(CORSOriginValidationMiddleware))
        return _original_http_app(middleware=middleware, **kwargs)

    app.http_app = _http_app


_wrap_http_app_with_security_middleware()

if __name__ == "__main__":
    if ENVIRONMENT == "production":
        logger.info(f"Starting RivalSearchMCP in production mode on port {PORT}")
        app.run(transport="http", host="0.0.0.0", port=PORT, log_level=LOG_LEVEL)
    else:
        logger.info("Starting RivalSearchMCP in development mode (stdio)")
        # For CLI compatibility, run directly with STDIO transport
        app.run()
