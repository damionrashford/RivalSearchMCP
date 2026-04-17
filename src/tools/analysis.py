"""
Analysis tools for FastMCP server.
Handles content analysis and end-to-end research workflows.
"""

import asyncio
import re
from typing import Annotated, Any, Dict, List, Literal, Optional

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools.tool import ToolResult
from pydantic import Field

from src.core.conflict import find_conflicts as _find_conflicts_core
from src.core.quality import assess_results, summarize_quality
from src.logging.logger import logger
from src.utils.markdown_formatter import format_research_analysis_markdown

# ── Enums surfaced to the MCP schema so agents see the exact set ────────────
ContentOperation = Literal[
    "retrieve",
    "stream",
    "analyze",
    "extract",
    "score",
    "find_conflicts",
]
ExtractionMethod = Literal["auto", "html", "text", "markdown"]
AnalysisType = Literal["general", "sentiment", "technical", "business"]
LinkType = Literal["all", "internal", "external", "images", "documents"]
ResearchMode = Literal["topic", "entity"]


def register_analysis_tools(mcp: FastMCP):
    """Register consolidated content operations tool."""

    @mcp.tool(
        annotations={
            "title": "Content Operations",
            "readOnlyHint": True,
            "openWorldHint": True,
            "destructiveHint": False,
            "idempotentHint": False,
        },
        timeout=90.0,
    )
    async def content_operations(
        operation: Annotated[
            ContentOperation,
            Field(
                description=(
                    "What to do:\n"
                    "  retrieve       - fetch `url` and return its text/html/markdown\n"
                    "  stream         - stream-fetch `url`\n"
                    "  analyze        - analyze `content` for key points / sentiment\n"
                    "  extract        - extract links from `url`\n"
                    "  score          - rate `urls` on quality signals\n"
                    "  find_conflicts - compare `urls` for numeric / date / polarity disagreements"
                ),
            ),
        ],
        url: Annotated[
            Optional[str],
            Field(
                description="Single URL for retrieve / stream / extract.",
                default=None,
            ),
        ] = None,
        urls: Annotated[
            Optional[List[str]],
            Field(
                description=(
                    "List of URLs for score (≤50) or find_conflicts (2-10). "
                    "Ignored for single-URL operations."
                ),
                default=None,
            ),
        ] = None,
        content: Annotated[
            Optional[str],
            Field(
                description="Content body for `analyze` operation.",
                default=None,
            ),
        ] = None,
        claim: Annotated[
            Optional[str],
            Field(
                description=(
                    "find_conflicts only: a specific claim to check for "
                    "support vs contradiction across `urls` (e.g. 'the "
                    "vaccine is safe')."
                ),
                default=None,
            ),
        ] = None,
        metadata: Annotated[
            Optional[List[Dict[str, Any]]],
            Field(
                description=(
                    "score only: per-URL metadata aligned with `urls` "
                    "(title, published, citationCount, etc.) to sharpen "
                    "the freshness and corroboration signals."
                ),
                default=None,
            ),
        ] = None,
        extraction_method: Annotated[
            ExtractionMethod,
            Field(
                description="retrieve only: output format.",
                default="auto",
            ),
        ] = "auto",
        analysis_type: Annotated[
            AnalysisType,
            Field(description="analyze only: analysis focus.", default="general"),
        ] = "general",
        max_links: Annotated[
            int,
            Field(description="extract only: max links returned.", default=100, ge=1, le=500),
        ] = 100,
        link_type: Annotated[
            LinkType,
            Field(description="extract only: which link category.", default="all"),
        ] = "all",
        extract_key_points: Annotated[
            bool,
            Field(description="analyze only: extract key points.", default=True),
        ] = True,
        summarize: Annotated[
            bool,
            Field(description="analyze only: produce a summary.", default=True),
        ] = True,
        include_metadata: Annotated[
            bool,
            Field(description="Include metadata in the response.", default=True),
        ] = True,
        ctx: Optional[Context] = None,
    ) -> ToolResult | str:
        """
        One tool for every URL/content-level operation. Pick `operation`,
        provide whichever of `url`, `urls`, `content` that operation
        needs, and leave the rest defaulted. Parameter annotations above
        (visible in the MCP schema) state which operation each parameter
        applies to.

        Quick map of operation -> required inputs:

          retrieve       url
          stream         url
          analyze        content
          extract        url
          score          urls              (optionally metadata)
          find_conflicts urls              (optionally claim)
        """
        try:
            logger.info(f"Performing {operation} operation")

            if operation == "retrieve":
                if not url:
                    raise ToolError("URL required for retrieve operation")

                # Dispatch on extraction_method to the right shared-client
                # helper. Scrapling's parser handles sites (Wikipedia, etc.)
                # where the previous BeautifulSoup+custom converter silently
                # produced empty output.
                from src.utils.scrapling_client import (
                    fetch_html,
                    fetch_markdown,
                    fetch_text,
                )

                max_retries = 3
                result: Optional[str] = None
                for attempt in range(max_retries):
                    try:
                        if extraction_method == "html":
                            result = await fetch_html(url)
                        elif extraction_method == "text":
                            result = await fetch_text(url)
                        else:  # markdown / auto
                            result = await fetch_markdown(url)
                        if result:
                            break
                    except Exception as e:
                        logger.warning(f"Content retrieval attempt {attempt + 1} failed: {e}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)

                if not result:
                    result = (
                        f"Failed to retrieve content from {url} after " f"{max_retries} attempts"
                    )
                return result

            elif operation == "stream":
                if not url:
                    raise ToolError("URL required for stream operation")
                # Real streaming implementation with retry logic
                from src.core.fetch import stream_fetch

                max_retries = 3
                content = None
                for attempt in range(max_retries):
                    try:
                        content = await stream_fetch(url)
                        if content:
                            break
                    except Exception as e:
                        logger.warning(f"Content streaming attempt {attempt + 1} failed: {e}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)

                if content:
                    result = str(content)
                else:
                    result = f"Failed to stream content from {url} after {max_retries} attempts"

                return result

            elif operation == "analyze":
                if not content:
                    raise ToolError("Content required for analyze operation")

                # Basic content analysis
                analysis_result = {
                    "content_length": len(content),
                    "word_count": len(content.split()),
                    "analysis_type": analysis_type,
                    "key_points": [],
                    "summary": "",
                    "insights": {},
                }

                # Extract key points if requested
                if extract_key_points:
                    sentences = re.split(r"[.!?]+", content)
                    sentences = [s.strip() for s in sentences if len(s.strip()) > 30]

                    scored_sentences = []
                    for sentence in sentences:
                        score = len(sentence) * 0.3
                        important_words = [
                            "important",
                            "key",
                            "critical",
                            "essential",
                            "significant",
                            "major",
                            "primary",
                        ]
                        for word in important_words:
                            if word.lower() in sentence.lower():
                                score += 10
                        scored_sentences.append((sentence, score))

                    scored_sentences.sort(key=lambda x: x[1], reverse=True)
                    key_points = [s[0] for s in scored_sentences[:5]]
                    analysis_result["key_points"] = key_points

                # Create summary if requested
                if summarize:
                    sentences = re.split(r"[.!?]+", content)
                    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

                    if len(sentences) > 3:
                        summary_parts = [
                            sentences[0],
                            sentences[len(sentences) // 2] if len(sentences) > 2 else "",
                            sentences[-1] if len(sentences) > 1 else "",
                        ]
                        summary = ". ".join([s for s in summary_parts if s])
                    else:
                        summary = content

                    analysis_result["summary"] = summary

                # Type-specific analysis
                if analysis_type == "sentiment":
                    positive_words = [
                        "good",
                        "great",
                        "excellent",
                        "amazing",
                        "wonderful",
                        "positive",
                        "happy",
                        "success",
                    ]
                    negative_words = [
                        "bad",
                        "terrible",
                        "awful",
                        "negative",
                        "sad",
                        "failure",
                        "problem",
                        "issue",
                    ]

                    content_lower = content.lower()
                    positive_count = sum(content_lower.count(word) for word in positive_words)
                    negative_count = sum(content_lower.count(word) for word in negative_words)

                    sentiment = (
                        "positive"
                        if positive_count > negative_count
                        else "negative" if negative_count > positive_count else "neutral"
                    )
                    analysis_result["insights"]["sentiment"] = sentiment

                elif analysis_type == "technical":
                    technical_patterns = [
                        r"\b[A-Z]{2,}\b",
                        r"\b\w+\.\w+\b",
                        r"\b\d+\.\d+\b",
                        r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)*\b",
                    ]
                    technical_terms = set()
                    for pattern in technical_patterns:
                        matches = re.findall(pattern, content)
                        technical_terms.update(matches)
                    analysis_result["insights"]["technical_terms"] = list(technical_terms)[:10]

                elif analysis_type == "business":
                    money_pattern = r"\$[\d,]+(?:\.\d{2})?"
                    percentage_pattern = r"\d+(?:\.\d+)?%"
                    date_pattern = r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
                    money_matches = re.findall(money_pattern, content)
                    percentage_matches = re.findall(percentage_pattern, content)
                    date_matches = re.findall(date_pattern, content)
                    analysis_result["insights"]["business_metrics"] = {
                        "monetary_values": money_matches[:5],
                        "percentages": percentage_matches[:5],
                        "dates": date_matches[:5],
                    }

                return format_research_analysis_markdown(
                    {
                        "topic": f"Content Analysis: {content[:50]}{'...' if len(content) > 50 else ''}",
                        "summary": analysis_result.get("summary", ""),
                        "key_findings": analysis_result.get("key_points", []),
                        "status": "success",
                    },
                    "Content Operations",
                )

            elif operation == "extract":
                if not url:
                    raise ToolError("URL required for extract operation")

                # Real link extraction implementation
                from urllib.parse import urljoin, urlparse

                from src.core.fetch import base_fetch_url

                try:
                    content = await base_fetch_url(url)
                    if not content:
                        return format_research_analysis_markdown(
                            {
                                "topic": f"Link Extraction from {url}",
                                "status": "error",
                                "error": "Failed to fetch content",
                            },
                            "Content Operations",
                        )

                    # Parse HTML and extract links
                    from bs4 import BeautifulSoup

                    soup = BeautifulSoup(str(content), "html.parser")

                    all_links = []
                    internal_links = []
                    external_links = []
                    image_links = []
                    document_links = []

                    base_domain = urlparse(url).netloc

                    # Extract <a> tags
                    for link in soup.find_all("a", href=True):
                        href = link.get("href", "")
                        if not href or href.startswith("#"):
                            continue

                        absolute_url = urljoin(url, href)
                        link_domain = urlparse(absolute_url).netloc

                        link_info = {
                            "url": absolute_url,
                            "text": link.get_text(strip=True)[:100] or "No text",
                            "type": "internal" if link_domain == base_domain else "external",
                        }

                        all_links.append(link_info)

                        if link_domain == base_domain:
                            internal_links.append(link_info)
                        else:
                            external_links.append(link_info)

                        # Check if it's a document
                        if any(
                            absolute_url.lower().endswith(ext)
                            for ext in [
                                ".pdf",
                                ".doc",
                                ".docx",
                                ".xls",
                                ".xlsx",
                                ".ppt",
                                ".pptx",
                                ".zip",
                            ]
                        ):
                            document_links.append(link_info)

                    # Extract images
                    for img in soup.find_all("img", src=True):
                        src = img.get("src", "")
                        absolute_url = urljoin(url, src)
                        image_links.append(
                            {
                                "url": absolute_url,
                                "alt": img.get("alt", "No alt text"),
                                "type": "image",
                            }
                        )

                    # Select links based on link_type
                    if link_type == "internal":
                        selected_links = internal_links
                    elif link_type == "external":
                        selected_links = external_links
                    elif link_type == "images":
                        selected_links = image_links
                    elif link_type == "documents":
                        selected_links = document_links
                    else:  # "all"
                        selected_links = all_links

                    # Limit to max_links
                    selected_links = selected_links[:max_links]

                    # Format result
                    result_summary = f"Extracted {len(selected_links)} {link_type} links from {url}"
                    key_findings = [
                        f"{link.get('text', link.get('alt', 'Link'))}: {link['url']}"
                        for link in selected_links[:10]
                    ]

                    if link_type == "all":
                        result_summary += f" ({len(internal_links)} internal, {len(external_links)} external, {len(image_links)} images, {len(document_links)} documents)"

                    return format_research_analysis_markdown(
                        {
                            "topic": f"Link Extraction: {url}",
                            "summary": result_summary,
                            "key_findings": key_findings,
                            "link_statistics": {
                                "total_links": len(all_links),
                                "internal_links": len(internal_links),
                                "external_links": len(external_links),
                                "image_links": len(image_links),
                                "document_links": len(document_links),
                                "extracted_type": link_type,
                                "extracted_count": len(selected_links),
                            },
                            "status": "success",
                        },
                        "Content Operations",
                    )

                except Exception as extract_error:
                    logger.error(f"Link extraction failed: {extract_error}")
                    return format_research_analysis_markdown(
                        {
                            "topic": f"Link Extraction from {url}",
                            "status": "error",
                            "error": str(extract_error),
                        },
                        "Content Operations",
                    )

            elif operation == "score":
                if not urls:
                    raise ToolError("urls list required for score operation")
                if len(urls) > 50:
                    raise ToolError("score operation accepts at most 50 urls")

                # Align optional metadata
                md = list(metadata or [])
                while len(md) < len(urls):
                    md.append({})
                seeded = [{"url": u, **(m or {})} for u, m in zip(urls, md)]
                annotated = assess_results(seeded)
                summary = summarize_quality(annotated)

                findings = [
                    f"{r['quality']['score']}/100 ({r['quality']['tier']}) — {r['url']}"
                    for r in annotated
                ]
                payload = {
                    "topic": "Source Quality Scores",
                    "summary": (
                        f"Confidence {summary['confidence']} · "
                        f"mean {summary['mean_score']}/100 · "
                        f"{summary['independent_domains']} independent domains across "
                        f"{summary['result_count']} sources"
                    ),
                    "key_findings": findings,
                    "quality_details": [{"url": r["url"], **r["quality"]} for r in annotated],
                    "confidence": summary,
                    "status": "success",
                }
                # Dual-channel return: LLMs read the markdown (content),
                # agents parse the raw scores from structured_content.
                return ToolResult(
                    content=format_research_analysis_markdown(payload, "Content Operations"),
                    structured_content=payload,
                )

            elif operation == "find_conflicts":
                if not urls or len(urls) < 2:
                    raise ToolError("find_conflicts requires a list of at least 2 urls")
                if len(urls) > 10:
                    raise ToolError("find_conflicts accepts at most 10 urls per call")

                # Fetch each URL via Scrapling (TLS-fingerprint safe) with
                # an httpx fallback, extract clean text, cap at 8000 chars
                # per source so the detector doesn't drown in noise.
                from scrapling.fetchers import AsyncFetcher

                from src.core.content.extractors import UnifiedContentExtractor

                extractor = UnifiedContentExtractor()

                # Progress: report once per source as it lands. Using a
                # counter + lock-free increment because asyncio.gather
                # coroutines run on the same thread in the event loop.
                fetch_total = len(urls)
                fetched = 0

                async def _snippet(target_url: str) -> str:
                    nonlocal fetched
                    try:
                        try:
                            page = await AsyncFetcher.get(
                                target_url, stealthy_headers=True, timeout=20
                            )
                            if page.status == 200 and page.body:
                                text = page.text or page.body.decode("utf-8", "replace")
                                return extractor.extract(text)[:8000]
                        except Exception as e:
                            logger.debug(
                                "find_conflicts Scrapling fetch failed for %s: %s",
                                target_url,
                                e,
                            )
                        try:
                            import httpx

                            async with httpx.AsyncClient(
                                timeout=20.0,
                                follow_redirects=True,
                                headers={"User-Agent": "rivalsearchmcp/1.0"},
                            ) as client:
                                r = await client.get(target_url)
                                if r.status_code == 200:
                                    return extractor.extract(r.text)[:8000]
                        except Exception as e:
                            logger.warning("find_conflicts fetch failed for %s: %s", target_url, e)
                        return ""
                    finally:
                        fetched += 1
                        if ctx is not None:
                            try:
                                await ctx.report_progress(
                                    progress=fetched,
                                    total=fetch_total,
                                    message=f"fetched {fetched}/{fetch_total} sources",
                                )
                            except Exception:
                                pass

                if ctx is not None:
                    try:
                        await ctx.report_progress(
                            progress=0,
                            total=fetch_total,
                            message=f"fetching {fetch_total} sources",
                        )
                    except Exception:
                        pass
                snippets = await asyncio.gather(*[_snippet(u) for u in urls])
                if ctx is not None:
                    try:
                        await ctx.report_progress(
                            progress=fetch_total,
                            total=fetch_total,
                            message="detecting conflicts",
                        )
                    except Exception:
                        pass
                report = _find_conflicts_core([s for s in snippets], claim=claim)

                findings: List[str] = []
                for c in report.conflicts:
                    findings.append(
                        f"[{c.type.value}] {c.topic} — "
                        f"{c.value_a} (src {c.source_a_index}) vs "
                        f"{c.value_b} (src {c.source_b_index}) — confidence {c.confidence:.0%}"
                    )
                if not findings:
                    findings = ["No conflicts detected across the provided sources."]

                payload = {
                    "topic": (
                        f"Conflict Analysis ({len(urls)} sources)"
                        + (f" — claim: {claim!r}" if claim else "")
                    ),
                    "summary": (
                        f"{len(report.conflicts)} disagreement(s) detected "
                        f"across {len(urls)} sources. "
                        f"{len(report.agreements)} agreement record(s)."
                    ),
                    "key_findings": findings,
                    "sources": [{"title": url, "url": url} for url in urls],
                    "conflicts": [c.as_dict() for c in report.conflicts],
                    "agreements": report.agreements,
                    "status": "success",
                }
                return ToolResult(
                    content=format_research_analysis_markdown(payload, "Content Operations"),
                    structured_content=payload,
                )

            else:
                raise ToolError(f"Unknown operation: {operation}")

        except Exception as e:
            logger.error(f"Content operations failed: {e}")
            return format_research_analysis_markdown(
                {"topic": "Content Operations", "status": "error", "error": str(e)},
                "Content Operations",
            )

        # This should never be reached, but ensures type safety
        return format_research_analysis_markdown(
            {
                "topic": "Content Operations",
                "status": "error",
                "error": "Unexpected execution path",
            },
            "Content Operations",
        )

    @mcp.tool(
        annotations={
            "title": "Research Topic",
            "readOnlyHint": True,
            "openWorldHint": True,
            "destructiveHint": False,
            "idempotentHint": False,
        },
        # Entity mode fans out to up to 8 sub-sources in parallel, each
        # with its own ~30s HTTP timeout. Topic mode is faster but also
        # chains search + per-result content fetch. 180s is a generous
        # ceiling -- the real constraint is each sub-source's own budget.
        timeout=180.0,
    )
    async def research_topic(
        topic: Annotated[
            str,
            Field(
                description=(
                    "Subject of the research. A topic or question in "
                    "`topic` mode (e.g. 'transformer attention'); an "
                    "entity name in `entity` mode (e.g. 'OpenAI', "
                    "'FastMCP', 'Linus Torvalds')."
                ),
                min_length=2,
                max_length=300,
            ),
        ],
        mode: Annotated[
            ResearchMode,
            Field(
                description=(
                    "topic  - search + fetch + extract findings from top sources.\n"
                    "entity - profile a named entity by fanning out across "
                    "web, news, GitHub, social, and academic sources in "
                    "parallel. Returns a unified multi-section report."
                ),
                default="topic",
            ),
        ] = "topic",
        sources: Annotated[
            Optional[List[str]],
            Field(
                description=(
                    "topic mode only: override the search step with these "
                    "specific URLs. Ignored in entity mode."
                ),
                default=None,
            ),
        ] = None,
        max_sources: Annotated[
            int,
            Field(
                description="Upper bound on sources per section.",
                ge=1,
                le=20,
                default=5,
            ),
        ] = 5,
        include_analysis: Annotated[
            bool,
            Field(
                description=(
                    "topic mode only: run key-findings extraction on " "retrieved content."
                ),
                default=True,
            ),
        ] = True,
        session_id: Annotated[
            Optional[str],
            Field(
                description=(
                    "If provided, findings are appended to the research "
                    "memory session with this id (see research_memory). "
                    "Enables iterative research across calls."
                ),
                default=None,
            ),
        ] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """
        End-to-end deterministic research workflow. One tool, two modes:

          topic  - open-ended search + fetch + extract
          entity - unified cross-source profile of a named entity

        Both modes auto-attach per-result quality scores and an aggregate
        confidence signal so callers can calibrate trust. When `session_id`
        is given, results are appended to research memory automatically.
        """
        try:
            if mode == "entity":
                return await _run_entity_mode(
                    topic, max_sources=max_sources, session_id=session_id, ctx=ctx
                )
            return await _run_topic_mode(
                topic,
                sources=sources,
                max_sources=max_sources,
                include_analysis=include_analysis,
                session_id=session_id,
            )
        except Exception as e:
            logger.error(f"Research topic failed: {e}")
            return format_research_analysis_markdown(
                {"topic": topic, "status": "error", "error": str(e)},
                "Topic Research",
            )


# ── Helpers used by research_topic modes ─────────────────────────────────────


async def _auto_save(session_id: Optional[str], findings: List[Dict[str, Any]]) -> None:
    """Best-effort append to a research memory session. Silent on failure
    so memory unavailability never breaks a research call."""
    if not session_id or not findings:
        return
    try:
        from src.core.memory import research_session_add

        await research_session_add(session_id, findings=findings)
    except Exception as e:
        logger.debug("auto-save to session %s failed: %s", session_id, e)


async def _run_topic_mode(
    topic: str,
    *,
    sources: Optional[List[str]],
    max_sources: int,
    include_analysis: bool,
    session_id: Optional[str],
) -> str:
    """Topic research: search + fetch + extract key findings, with
    automatic quality scoring and optional session memory. Routes
    through the shared Scrapling client so Cloudflare/Akamai-fronted
    sites respond 200 instead of 403."""
    from src.utils.scrapling_client import fetch_text

    logger.info("Starting comprehensive research on: %s", topic)

    if not sources:
        from src.core.search.engines.duckduckgo.duckduckgo_engine import (
            DuckDuckGoSearchEngine,
        )

        engine = DuckDuckGoSearchEngine()
        results = await engine.search(query=topic, num_results=max_sources)
        sources = [r.url for r in results[:max_sources] if r.url]

    sources_researched: List[Dict[str, Any]] = []
    key_findings: List[str] = []

    # Relevance-weighted sentence selection:
    # the longer the sentence AND the more query tokens it contains,
    # the more it contributes to the score. Replaces the old keyword-gated
    # filter that missed substantive sentences lacking the exact words
    # "important / key / critical / significant".
    query_tokens = {t.lower() for t in re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", topic)}

    def _rank_sentence(s: str) -> float:
        if len(s) < 40 or len(s) > 600:
            return 0.0
        lower = s.lower()
        tok_hits = sum(1 for t in query_tokens if t in lower) if query_tokens else 0
        # Density-ish signal: hits × log(length).
        import math

        length_score = math.log10(max(1, len(s)) + 1) - 1.5  # 0 at ~30 chars
        return max(0.0, length_score) * (1 + 0.5 * tok_hits)

    for source_url in sources:
        try:
            clean_content = await fetch_text(source_url)
            if not clean_content:
                continue
            sources_researched.append(
                {
                    "url": source_url,
                    "title": source_url,
                    "content": clean_content,
                    "content_length": len(clean_content),
                }
            )
            if include_analysis:
                sentences = re.split(r"(?<=[.!?])\s+", clean_content)
                ranked = sorted(
                    ((s.strip(), _rank_sentence(s)) for s in sentences),
                    key=lambda pair: pair[1],
                    reverse=True,
                )
                key_findings.extend(s for s, score in ranked[:3] if score > 0)
        except Exception as e:
            logger.warning("Failed to retrieve content from %s: %s", source_url, e)

    # Auto-attach quality + aggregate confidence.
    scored = assess_results(sources_researched)
    confidence = summarize_quality(scored)

    summary = (
        (
            f"Research on '{topic}': {len(scored)} sources, "
            f"{len(key_findings)} key findings. "
            f"Confidence {confidence['confidence']} "
            f"(mean {confidence['mean_score']}/100, "
            f"{confidence['independent_domains']} independent domains)."
        )
        if scored
        else f"Research on '{topic}': no sources retrieved."
    )

    await _auto_save(session_id, scored)

    return format_research_analysis_markdown(
        {
            "topic": topic,
            "summary": summary,
            "key_findings": key_findings,
            "sources": scored,
            "confidence": confidence,
            "status": "success",
        },
        "Topic Research",
    )


async def _report(ctx: Optional[Context], progress: float, total: float, message: str) -> None:
    """Best-effort progress reporter. Silent if no context is bound or the
    client doesn't care. Keeps phase-boundary calls from having to repeat
    the same try/except boilerplate."""
    if ctx is None:
        return
    try:
        await ctx.report_progress(progress=progress, total=total, message=message)
    except Exception:
        pass


async def _run_entity_mode(
    entity: str,
    *,
    max_sources: int,
    session_id: Optional[str],
    ctx: Optional[Context] = None,
) -> str:
    """Unified cross-source entity profile: web + news + github + social
    + academic fanned out in parallel, per-result quality, aggregate
    confidence, optional session persistence."""
    from src.core.news.aggregator import NewsAggregator
    from src.core.scientific.search.orchestrator import AcademicSearchOrchestrator
    from src.core.social.bluesky import BlueskySearch
    from src.core.social.hackernews import HackerNewsSearch
    from src.core.social.reddit import RedditSearch
    from src.core.social.stackoverflow import StackOverflowSearch
    from src.tools.multi_search import MultiSearchOrchestrator

    logger.info("Profiling entity: %s", entity)

    tasks: Dict[str, Any] = {
        "web": MultiSearchOrchestrator().search_all_engines(
            query=entity,
            num_results=max_sources,
            extract_content=False,
            follow_links=False,
            max_depth=1,
        ),
        "news": NewsAggregator().search_news(
            query=entity, max_results=max_sources, time_range="month"
        ),
        "hn": HackerNewsSearch().search(query=entity, limit=max_sources),
        "reddit": RedditSearch().search(
            query=entity, subreddit="all", limit=max_sources, time_filter="month"
        ),
        "so": StackOverflowSearch().search(query=entity, site="stackoverflow", limit=max_sources),
        "bsky": BlueskySearch().search(query=entity, limit=max_sources),
        "academic": AcademicSearchOrchestrator().search_academic_papers(
            query=entity,
            sources=["openalex", "crossref", "arxiv"],
            limit=max_sources,
        ),
    }

    try:
        from src.core.github_api.search import GitHubSearch

        tasks["github"] = GitHubSearch().search_repositories(query=entity, per_page=max_sources)
    except Exception as e:
        logger.debug("github fan-out skipped: %s", e)

    # 4 phases: fan-out, normalize, score, aggregate. Reported on a 0-100
    # scale so clients can render a consistent bar regardless of how many
    # sub-sources ran this time.
    await _report(ctx, 10, 100, f"fanning out to {len(tasks)} sources")

    names = list(tasks.keys())
    outs = await asyncio.gather(*tasks.values(), return_exceptions=True)
    by_name = dict(zip(names, outs))

    await _report(ctx, 55, 100, "fan-out complete, normalizing results")

    sections: Dict[str, List[Dict[str, Any]]] = {
        "web": [],
        "news": [],
        "github": [],
        "social": [],
        "academic": [],
    }
    failures: Dict[str, str] = {}

    web = by_name.get("web")
    if isinstance(web, Exception):
        failures["web"] = str(web)
    elif isinstance(web, dict):
        for engine_data in (web.get("results") or {}).values():
            for r in (engine_data or {}).get("results", []):
                if isinstance(r, dict):
                    sections["web"].append(r)
                elif hasattr(r, "to_dict"):
                    sections["web"].append(r.to_dict())

    news = by_name.get("news")
    if isinstance(news, Exception):
        failures["news"] = str(news)
    elif news:
        sections["news"] = list(news)

    github = by_name.get("github")
    if isinstance(github, Exception):
        failures["github"] = str(github)
    elif github:
        for r in github:
            if "url" not in r and "html_url" in r:
                r["url"] = r["html_url"]
            sections["github"].append(r)

    for key in ("hn", "reddit", "so", "bsky"):
        data = by_name.get(key)
        if isinstance(data, Exception):
            failures[key] = str(data)
        elif data:
            for item in data:
                if "text" in item and "title" not in item:
                    item["title"] = item["text"][:120]
                sections["social"].append(item)

    academic = by_name.get("academic")
    if isinstance(academic, Exception):
        failures["academic"] = str(academic)
    elif academic:
        sections["academic"] = list(academic)

    await _report(ctx, 75, 100, "scoring results")

    for key in list(sections.keys()):
        sections[key] = assess_results(sections[key])[:max_sources]

    # Aggregate confidence across the union
    union = [it for items in sections.values() for it in items]
    union_annotated = assess_results(
        [{k: v for k, v in it.items() if k != "quality"} for it in union]
    )
    confidence = summarize_quality(union_annotated)

    await _report(ctx, 90, 100, "aggregating confidence")

    # Flatten for auto-save
    flat_findings: List[Dict[str, Any]] = []
    for section_name, items in sections.items():
        for it in items:
            enriched = dict(it)
            enriched.setdefault("section", section_name)
            flat_findings.append(enriched)
    await _auto_save(session_id, flat_findings)
    await _report(ctx, 100, 100, "done")

    # Render a structured multi-section report
    md = f"# 🗺️ Entity Profile: *{entity}*\n\n"
    badge = {"high": "🟢", "medium": "🟡", "low": "🔴", "none": "⚪"}.get(
        confidence["confidence"], "⚪"
    )
    md += (
        f"**{badge} Confidence:** {confidence['confidence']} · "
        f"mean quality {confidence['mean_score']}/100 · "
        f"{confidence['independent_domains']} independent sources across "
        f"{confidence['result_count']} results\n\n---\n\n"
    )

    section_titles = {
        "web": "🌐 Web Overview",
        "news": "📰 Recent News",
        "github": "🐙 Code & Community",
        "social": "💬 Community Sentiment",
        "academic": "🔬 Academic Footprint",
    }
    for key, title in section_titles.items():
        items = sections.get(key, [])
        if not items:
            continue
        md += f"## {title}\n\n"
        for i, it in enumerate(items[:5], 1):
            heading = it.get("title") or it.get("name") or it.get("text", "")[:80]
            md += f"### {i}. {heading}\n\n"
            q = it.get("quality") or {}
            if q:
                md += f"**Quality:** {q.get('score', 0)}/100 " f"({q.get('tier', '?')})"
                sig = q.get("signals") or {}
                if sig.get("corroboration"):
                    md += f" · corroborated by {sig['corroboration']} other sources"
                md += "\n\n"
            if it.get("description"):
                md += f"{it['description'][:300]}\n\n"
            url = it.get("url") or it.get("link")
            if url:
                md += f"[🔗 Source]({url})\n\n"
            md += "---\n\n"

    if failures:
        md += "## ⚠️ Source Notes\n\n"
        for src_name, err in failures.items():
            md += f"- **{src_name}**: {err}\n"
        md += "\n"

    if session_id:
        md += f"*Saved to research session `{session_id}`.*\n\n"

    return md
