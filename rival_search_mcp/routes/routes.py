"""
Custom routes for RivalSearchMCP server.
Provides health checks, metrics, and monitoring endpoints.
"""

import os
from datetime import datetime

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.status import HTTP_200_OK, HTTP_500_INTERNAL_SERVER_ERROR

from rival_search_mcp.logging.logger import logger
from rival_search_mcp.performance.performance import performance_monitor


def register_custom_routes(mcp):
    """Register custom routes with the FastMCP server."""

    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request: Request) -> PlainTextResponse:
        """Health check endpoint for monitoring."""
        return PlainTextResponse(content="OK", status_code=HTTP_200_OK)

    @mcp.custom_route("/metrics", methods=["GET"])
    async def metrics_endpoint(request: Request) -> JSONResponse:
        """Comprehensive metrics endpoint for monitoring and observability."""
        try:
            from rival_search_mcp.core.metrics.metrics import get_metrics_collector

            # Get comprehensive metrics
            collector = get_metrics_collector()
            all_metrics = await collector.get_all_metrics()

            return JSONResponse(content=all_metrics, status_code=HTTP_200_OK)

        except Exception as e:
            logger.error(f"Metrics endpoint failed: {e}")
            return JSONResponse(
                content={"error": str(e)}, status_code=HTTP_500_INTERNAL_SERVER_ERROR
            )

    @mcp.custom_route("/metrics/prometheus", methods=["GET"])
    async def prometheus_metrics_endpoint(request: Request) -> PlainTextResponse:
        """Prometheus-compatible metrics endpoint."""
        try:
            from rival_search_mcp.core.metrics.metrics import get_metrics_collector

            collector = get_metrics_collector()
            prometheus_output = collector.get_prometheus_metrics()

            return PlainTextResponse(content=prometheus_output, status_code=HTTP_200_OK)

        except Exception as e:
            logger.error(f"Prometheus metrics endpoint failed: {e}")
            return PlainTextResponse(
                content=f"# Error: {e}", status_code=HTTP_500_INTERNAL_SERVER_ERROR
            )

    @mcp.custom_route("/status", methods=["GET"])
    async def status_endpoint(request: Request) -> JSONResponse:
        """Detailed status endpoint for comprehensive server information."""
        try:
            status_data = {
                "server": {
                    "name": "RivalSearchMCP",
                    "version": "2.0.0",
                    "status": "operational",
                    "timestamp": datetime.now().isoformat(),
                },
                "environment": {
                    "environment": os.getenv("ENVIRONMENT", "development"),
                    "port": os.getenv("PORT", "8000"),
                    "log_level": os.getenv("LOG_LEVEL", "INFO"),
                },
                "capabilities": {
                    "search": True,
                    "traversal": True,
                    "analysis": True,
                    "retrieval": True,
                },
                "performance": {
                    "uptime_seconds": performance_monitor.get_overall_stats().get(
                        "uptime_seconds", 0
                    ),
                    "total_operations": performance_monitor.get_overall_stats().get(
                        "total_operations", 0
                    ),
                    "success_rate": performance_monitor.get_overall_stats().get(
                        "overall_success_rate", 0
                    ),
                },
            }

            return JSONResponse(content=status_data, status_code=HTTP_200_OK)

        except Exception as e:
            logger.error(f"Status endpoint failed: {e}")
            return JSONResponse(
                content={"error": str(e)}, status_code=HTTP_500_INTERNAL_SERVER_ERROR
            )

    @mcp.custom_route("/info", methods=["GET"])
    async def info_endpoint(request: Request) -> JSONResponse:
        """Information endpoint for server details and configuration."""
        try:
            info_data = {
                "server_info": {
                    "name": "RivalSearchMCP",
                    "description": "Advanced Web Research and Content Discovery MCP Server",
                    "version": "2.0.0",
                    "author": "RivalSearchMCP Team",
                    "license": "MIT",
                },
                "features": {
                    "cloudflare_bypass": True,
                    "rich_snippets": True,
                    "traffic_estimation": True,
                    "ocr_support": True,
                    "multi_engine_fallback": True,
                    "comprehensive_research": True,
                },
                "tools": {
                    "search": ["web_search", "social_search", "news_aggregation", "github_search"],
                    "traversal": ["map_website"],
                    "analysis": ["content_operations", "research_topic"],
                    "scientific": ["scientific_research"],
                    "documents": ["document_analysis"],
                },
                "endpoints": {
                    "health": "/health",
                    "metrics": "/metrics",
                    "status": "/status",
                    "info": "/info",
                },
            }

            return JSONResponse(content=info_data, status_code=HTTP_200_OK)

        except Exception as e:
            logger.error(f"Info endpoint failed: {e}")
            return JSONResponse(
                content={"error": str(e)}, status_code=HTTP_500_INTERNAL_SERVER_ERROR
            )

    @mcp.custom_route("/performance", methods=["GET"])
    async def performance_endpoint(request: Request) -> JSONResponse:
        """Performance analysis endpoint with recommendations."""
        try:
            from rival_search_mcp.performance.performance import create_performance_report

            performance_report = create_performance_report()

            return JSONResponse(content=performance_report, status_code=HTTP_200_OK)

        except Exception as e:
            logger.error(f"Performance endpoint failed: {e}")
            return JSONResponse(
                content={"error": str(e)}, status_code=HTTP_500_INTERNAL_SERVER_ERROR
            )

    @mcp.custom_route("/tools", methods=["GET"])
    async def tools_endpoint(request: Request) -> JSONResponse:
        """Tools information endpoint."""
        try:
            tools_info = {
                "search": {
                    "web_search": {
                        "description": "Multi-engine web search (DuckDuckGo, Bing, Yahoo, Mojeek, Wikipedia, optional You.com when YDC_API_KEY is set)",
                        "parameters": ["query", "num_results", "search_type"],
                    },
                    "social_search": {
                        "description": "Search across Reddit, Hacker News, Dev.to, Product Hunt, Medium, Stack Overflow, Bluesky, Lobste.rs, Lemmy",
                        "parameters": ["query", "platforms", "max_results"],
                    },
                    "news_aggregation": {
                        "description": "News from Google News, Bing News, Guardian, GDELT, DuckDuckGo News",
                        "parameters": ["query", "max_results", "language", "country", "time_range"],
                    },
                    "github_search": {
                        "description": "Search GitHub repositories via public API",
                        "parameters": ["query", "language", "sort", "order", "per_page"],
                    },
                    "scientific_research": {
                        "description": "Academic papers (OpenAlex, CrossRef, arXiv, PubMed, Europe PMC) and datasets (Kaggle, HuggingFace, Zenodo, Harvard Dataverse)",
                        "parameters": ["query", "operation", "sources", "max_results"],
                    },
                    "map_website": {
                        "description": "Structured website crawling in research, docs, or map mode",
                        "parameters": ["url", "mode", "max_pages", "max_depth"],
                    },
                },
                "content": {
                    "content_operations": {
                        "description": "URL/content transforms: retrieve, stream, analyze, extract, score, find_conflicts",
                        "parameters": ["operation", "url", "urls", "content"],
                    },
                    "document_analysis": {
                        "description": "Analyze PDF, DOCX, and text documents",
                        "parameters": ["source", "operation", "query"],
                    },
                },
                "research": {
                    "research_topic": {
                        "description": "Open-ended research (topic mode) or cross-source entity profiling (entity mode)",
                        "parameters": ["topic", "mode", "max_sources", "session_id"],
                    },
                },
            }

            return JSONResponse(content=tools_info, status_code=HTTP_200_OK)

        except Exception as e:
            logger.error(f"Tools endpoint failed: {e}")
            return JSONResponse(
                content={"error": str(e)}, status_code=HTTP_500_INTERNAL_SERVER_ERROR
            )

    logger.info("Custom routes registered successfully")
