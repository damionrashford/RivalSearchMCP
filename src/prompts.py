"""
Intelligent prompts for RivalSearchMCP.
Guides users on effective tool usage patterns.
"""

from fastmcp import FastMCP
from fastmcp.prompts import Message


def register_prompts(mcp: FastMCP):
    """Register all prompts for RivalSearchMCP."""

    @mcp.prompt
    def comprehensive_research(topic: str, depth: str = "comprehensive") -> list[Message]:
        """
        Guide the caller's LLM through an end-to-end research workflow using
        only the deterministic RivalSearchMCP tools. No in-server LLM is
        invoked -- the caller's model does the synthesis.

        Args:
            topic: The research topic or question
            depth: Research depth (basic, comprehensive, expert)
        """
        num_sources = {"basic": 5, "comprehensive": 10, "expert": 20}.get(depth, 10)
        return [
            Message(
                f"""Conduct {depth} research on: {topic}

Use this tool sequence and synthesize the results yourself:

1. entity_research (if the topic is a named entity) for a unified
   cross-source profile with per-item quality scores.
   - entity: "{topic}"

2. web_search for broader coverage.
   - query: "{topic}"
   - num_results: {num_sources}

3. news_aggregation for recent developments.
   - query: "{topic}"
   - max_results: {num_sources}
   - time_range: "month"

4. scientific_research if the topic has academic depth.
   - operation: "academic_search"
   - query: "{topic}"
   - max_results: {num_sources}

5. score_sources on the 5-10 most relevant URLs to calibrate trust
   before weighting findings.

6. find_conflicts when two or more sources make specific factual
   claims about the same referent -- surfaces disagreements as a
   first-class signal rather than averaging them away.

Then produce a report including:
- Key findings (weight by source quality, call out corroboration)
- Any conflicts surfaced by find_conflicts (explicitly)
- Confidence level and why
- Gaps / open questions worth a follow-up run""",
            )
        ]

    @mcp.prompt
    def multi_source_search(
        query: str, include_social: bool = True, include_news: bool = True
    ) -> list[Message]:
        """
        Search across multiple sources (web, social, news) and synthesize results.

        Guides the workflow: web_search → social_search → news_aggregation → synthesis

        Args:
            query: Search query
            include_social: Whether to include social media search
            include_news: Whether to include news aggregation
        """
        steps = [f"""Search for information about: {query}

Follow this research workflow:

1. First, use web_search to find general information:
   - query: "{query}"
   - num_results: 5"""]

        if include_social:
            steps.append("""
2. Then, use social_search to find community discussions:
   - platforms: ["reddit", "hackernews", "devto"]
   - max_results_per_platform: 5""")

        if include_news:
            steps.append("""
3. Next, use news_aggregation to find recent news:
   - max_results: 5""")

        steps.append("""
Finally, analyze all the information gathered and provide:
- Summary of web search findings
- Key insights from social discussions
- Recent developments from news
- Comprehensive synthesis of all sources""")

        return [Message("\n".join(steps))]

    @mcp.prompt
    def deep_content_analysis(url: str, extract_documents: bool = False) -> list[Message]:
        """
        Perform deep analysis of a website and its content.

        Guides workflow: map_website → content_operations → document_analysis

        Args:
            url: Website URL to analyze
            extract_documents: Whether to analyze linked documents (PDFs, etc.)
        """
        prompt = f"""Perform a deep analysis of this website: {url}

Follow this workflow:

1. Use map_website to explore the site structure:
   - url: "{url}"
   - mode: "research"
   - max_pages: 10

2. For interesting pages found, use content_operations to retrieve full content:
   - operation: "retrieve"
   - extraction_method: "markdown"

3. Use content_operations to extract all links:
   - operation: "extract"
   - link_type: "all"
"""

        if extract_documents:
            prompt += """
4. For any PDF or document links found, use document_analysis:
   - Extract text with OCR support
   - Analyze document content
"""

        prompt += """
Finally, provide:
- Website structure overview
- Key content themes
- Important pages and their purposes
- Document summaries (if applicable)
- Comprehensive site analysis"""

        return [Message(prompt)]

    @mcp.prompt
    def academic_literature_review(research_question: str, max_papers: int = 10) -> list[Message]:
        """
        Conduct an academic literature review with document analysis.

        Guides workflow: scientific_research → document_analysis → synthesis

        Args:
            research_question: The research question or topic
            max_papers: Maximum number of papers to review
        """
        return [
            Message(
                f"""Conduct an academic literature review on: {research_question}

Follow this research workflow:

1. Use scientific_research to find relevant papers:
   - operation: "academic_search"
   - query: "{research_question}"
   - max_results: {max_papers}
   - sources: ["openalex", "crossref", "arxiv", "europepmc"]

2. For papers with PDF links, use document_analysis to extract full text:
   - Extract text from PDFs
   - Use OCR for scanned papers if needed

3. Analyze and synthesize the findings:
   - Identify common themes and patterns
   - Note contradictions or debates
   - Highlight key methodologies
   - Summarize main conclusions

Provide a comprehensive literature review including:
- Overview of the research landscape
- Key papers and their contributions
- Common methodologies and approaches
- Research gaps and future directions
- Citations and references""",
            )
        ]
