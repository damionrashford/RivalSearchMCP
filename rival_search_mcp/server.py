#!/usr/bin/env python3
"""
RivalSearchMCP Server - Advanced Web Research and Content Discovery
"""

import os

from fastmcp import FastMCP

from rival_search_mcp.logging.logger import logger
from rival_search_mcp.middleware import register_middleware
from rival_search_mcp.middleware.cors_validation import CORSOriginValidationMiddleware
from rival_search_mcp.middleware.middleware import start_background_tasks
from rival_search_mcp.middleware.null_id_validation import NullIdValidationMiddleware
from rival_search_mcp.prompts import register_prompts
from rival_search_mcp.routes.routes import register_custom_routes
from rival_search_mcp.tools.analysis import register_analysis_tools
from rival_search_mcp.tools.github_tool import register_github_tools
from rival_search_mcp.tools.news import register_news_tools
from rival_search_mcp.tools.pdf_tool import register_pdf_tools
from rival_search_mcp.tools.scientific import register_scientific_tools
from rival_search_mcp.tools.search import register_search_tools
from rival_search_mcp.tools.social_media import register_social_media_tools
from rival_search_mcp.tools.traversal import register_traversal_tools

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

🛠️  AVAILABLE TOOLS (9):

Search (every result auto-annotated with a `quality` block + an
aggregate `confidence` summary — high / medium / low):
- web_search: DuckDuckGo + Bing + Yahoo + Mojeek + Wikipedia, with
  optional You.com when `YDC_API_KEY` is set
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
- document_analysis: PDF, DOCX, text, images (OCR) — up to 50MB.

📋 USAGE PATTERNS:

1. Quick search: web_search → content_operations(operation="retrieve")
   → document_analysis for PDFs
2. Entity profile: research_topic(mode="entity", topic=...) — one call
   fans out across every source and returns a unified report
3. Trust check: content_operations(operation="score", urls=[...])
4. Conflict check: content_operations(operation="find_conflicts",
   urls=[...], claim?=...)
5. Academic: scientific_research(operation="academic_search") →
   document_analysis on PDF links

💡 BEST PRACTICES:
- Every search tool attaches `quality` per result — weight findings by
  it when synthesizing; treat `confidence="low"` as a cue to cross-check
- Combine tools: search → score → retrieve → analyze → conflicts

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

# mask_error_details=True: generic exceptions surface as "Tool execution
# failed". Validation errors must raise ToolError to pass through unmasked.
app = FastMCP(
    name="RivalSearchMCP",
    instructions=SERVER_INSTRUCTIONS,
    on_duplicate="error",
    mask_error_details=True,
)

register_middleware(app)

register_search_tools(app)
register_traversal_tools(app)
register_analysis_tools(app)
register_scientific_tools(app)
register_social_media_tools(app)
register_news_tools(app)
register_github_tools(app)
register_pdf_tools(app)

register_prompts(app)
register_custom_routes(app)

start_background_tasks()


def _wrap_http_app_with_security_middleware():
    """Wrap app.http_app() so FastMCP Cloud, which calls it directly and
    never enters __main__, still gets the CORS + null-id validators."""
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
