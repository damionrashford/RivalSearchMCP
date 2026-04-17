"""
Scientific research tools for FastMCP server.
Provides academic paper search and dataset discovery using refactored modules.
"""

from typing import List, Optional

from fastmcp import Context, FastMCP
from pydantic import Field
from typing_extensions import Annotated

from src.core.scientific.datasets.orchestrator import DatasetDiscoveryOrchestrator
from src.core.scientific.search.orchestrator import AcademicSearchOrchestrator
from src.logging.logger import logger
from src.utils.markdown_formatter import (
    format_academic_search_markdown,
    format_dataset_discovery_markdown,
)


def register_scientific_tools(mcp: FastMCP):
    """Register scientific research tools using refactored orchestrators."""

    academic_orchestrator = AcademicSearchOrchestrator()
    dataset_orchestrator = DatasetDiscoveryOrchestrator()

    @mcp.tool(
        annotations={
            "title": "Scientific Research",
            "readOnlyHint": True,
            "openWorldHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
        timeout=120.0,
    )
    async def scientific_research(
        ctx: Context,
        operation: Annotated[
            str, Field(description="Operation type: 'academic_search' or 'dataset_discovery'")
        ],
        query: Annotated[str, Field(description="Search query", min_length=1, max_length=500)],
        max_results: Annotated[
            int, Field(description="Maximum results to return", ge=1, le=50, default=10)
        ] = 10,
        sources: Annotated[
            Optional[List[str]], Field(description="Specific sources to search (optional)")
        ] = None,
        categories: Annotated[
            Optional[List[str]], Field(description="Categories for dataset discovery (optional)")
        ] = None,
    ) -> str:
        """
        Scientific research tool for academic papers and datasets.

        Supports two operations:
        - academic_search: Search for academic papers across multiple sources
        - dataset_discovery: Discover datasets from various repositories

        Sources for academic_search (all keyless, queried concurrently):
          - openalex         ~240M works, strong full-text search, OA-aware
          - crossref         ~140M DOI-registered works (journals, books,
                             conference proceedings, preprints)
          - arxiv            physics/math/CS/stats/q-bio/q-fin preprints
          - pubmed           NCBI biomedical index
          - europepmc        biomedical + bioRxiv/medRxiv preprints

        semantic_scholar is no longer enabled by default -- the public
        Graph API 429-rate-limits anonymous callers into uselessness and
        there is no working scrape path (the SPA renders client-side).
        OpenAlex covers the same ~240M-work surface area with no key.
        Set SEMANTIC_SCHOLAR_API_KEY in the environment to re-enable it.

        Sources for dataset_discovery:
          - kaggle           Kaggle datasets list endpoint
          - huggingface      HuggingFace Hub datasets
          - zenodo           CERN's open-science repository (CC-licensed)
          - dataverse        Harvard Dataverse (largest research-data repo)

        Defaults pick the highest-recall combination per operation; pass
        `sources=[...]` to restrict.
        """
        try:
            if ctx:
                await ctx.report_progress(progress=0, total=100)
                await ctx.info(f"🔬 Performing {operation} for: {query}")

            if operation == "academic_search":
                if sources is None:
                    # OpenAlex + CrossRef give broadest keyless coverage;
                    # arxiv for preprints.
                    sources = ["openalex", "crossref", "arxiv"]

                result = await academic_orchestrator.search_academic_papers(
                    query=query, sources=sources, limit=max_results
                )

                # Auto-attach quality scores + aggregate confidence.
                try:
                    from src.core.quality import assess_results, summarize_quality

                    result = assess_results(result)
                    confidence = summarize_quality(result)
                except Exception as e:
                    logger.warning("scientific_research quality scoring failed: %s", e)
                    confidence = None

                formatted_result = format_academic_search_markdown(
                    {
                        "status": "success",
                        "query": query,
                        "results": result,
                        "metadata": {
                            "total_results": len(result),
                            "sources_used": sources,
                            "timestamp": "now",
                            **({"confidence": confidence} if confidence else {}),
                        },
                    }
                )

            elif operation == "dataset_discovery":
                if categories is None:
                    categories = ["computer_science"]

                result = await dataset_orchestrator.search_datasets(
                    query=query, sources=sources, limit=max_results
                )

                try:
                    from src.core.quality import assess_results, summarize_quality

                    result = assess_results(result)
                    confidence = summarize_quality(result)
                except Exception as e:
                    logger.warning("dataset_discovery quality scoring failed: %s", e)
                    confidence = None

                formatted_result = format_dataset_discovery_markdown(
                    {
                        "status": "success",
                        "query": query,
                        "datasets": result,
                        "metadata": {
                            "total_results": len(result),
                            "categories_searched": categories,
                            "timestamp": "now",
                            **({"confidence": confidence} if confidence else {}),
                        },
                    }
                )

            else:
                formatted_result = format_academic_search_markdown(
                    {
                        "status": "error",
                        "error": f"Unknown operation: {operation}",
                        "query": query,
                    }
                )

            if ctx:
                await ctx.report_progress(progress=100, total=100)

            return formatted_result

        except Exception as e:
            logger.error(f"Scientific research failed: {e}")
            error_result = {
                "status": "error",
                "error": str(e),
                "query": query,
                "operation": operation,
            }

            if "dataset" in operation:
                return format_dataset_discovery_markdown(error_result)
            else:
                return format_academic_search_markdown(error_result)
