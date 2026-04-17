"""
DuckDuckGo search engine implementation for RivalSearchMCP.

The search-page request at html.duckduckgo.com is fronted by DDG's
anti-bot layer, which returns HTTP 202 + an empty results page to
plain httpx (Python's default TLS fingerprint is not a browser).
Scrapling's AsyncFetcher with stealthy_headers=True drives tls_client
with a real browser fingerprint and a realistic header set, so DDG
serves the normal results HTML.

Content fetching for result URLs stays on httpx (BaseSearchEngine's
shared session); most target sites don't bot-check us.
"""

from datetime import datetime
from typing import List

from scrapling.fetchers import AsyncFetcher

from src.logging.logger import logger

from ...core.multi_engines import BaseSearchEngine, MultiSearchResult


class DuckDuckGoSearchEngine(BaseSearchEngine):
    """DuckDuckGo search via html.duckduckgo.com (Scrapling-powered)."""

    def __init__(self):
        super().__init__("DuckDuckGo", "https://duckduckgo.com")
        self.search_url = "https://html.duckduckgo.com/html/"

    async def search(
        self,
        query: str,
        num_results: int = 10,
        extract_content: bool = True,
        follow_links: bool = True,
        max_depth: int = 2,
    ) -> List[MultiSearchResult]:
        """Search DuckDuckGo and optionally extract result-page content."""
        logger.info("Starting DuckDuckGo search for: %s", query)

        results = await self._search_html(query, num_results)
        logger.info("DuckDuckGo returned %d results", len(results))

        if extract_content and results:
            for result in results:
                result.real_url = self._extract_real_url(result.url)
                target_url = result.real_url if result.real_url != result.url else result.url
                if not target_url:
                    continue

                content = await self._fetch_page_content(target_url)
                if not content:
                    continue

                result.full_content = self._extract_main_content(content)
                result.internal_links = self._extract_internal_links(content, target_url)
                result.html_structure = self._extract_html_structure(content)

                if follow_links and result.internal_links and max_depth > 1:
                    result.second_level_content = await self._extract_second_level_content(
                        target_url, result.internal_links
                    )

        return results

    async def _search_html(self, query: str, num_results: int) -> List[MultiSearchResult]:
        """Query html.duckduckgo.com via Scrapling and parse result cards."""
        try:
            page = await AsyncFetcher.get(
                f"{self.search_url}?q={query}",
                stealthy_headers=True,
                timeout=30,
            )
        except Exception as e:
            logger.error("DuckDuckGo fetch failed: %s", e)
            return []

        if page.status != 200:
            logger.warning(
                "DuckDuckGo returned %s for %r (body snippet: %s)",
                page.status,
                query,
                (page.text or "")[:200],
            )
            return []

        results: List[MultiSearchResult] = []
        # DDG html page: results are <div class="result"> with an
        # <a class="result__a"> title link and <a class="result__snippet">
        # snippet. Scrapling .css returns a Selectors list (not a single
        # element), so index into it.
        cards = page.css("div.result")
        for i, card in enumerate(cards[:num_results]):
            title_links = card.css("a.result__a")
            if not title_links:
                continue
            title_link = title_links[0]
            title = self._clean_text(title_link.text or "")
            raw_href = title_link.attrib.get("href", "")
            if not title or not raw_href:
                continue

            # DDG serves results wrapped in a `/l/?uddg=<target>` redirect
            # (often protocol-relative: `//duckduckgo.com/l/...`). Unwrap
            # here so downstream consumers get real target URLs instead
            # of DDG redirect stubs.
            url = _unwrap_ddg_url(raw_href)
            if not url:
                continue

            snippet_els = card.css("a.result__snippet, div.result__snippet")
            description = self._clean_text(snippet_els[0].text) if snippet_els else ""

            results.append(
                MultiSearchResult(
                    title=title,
                    url=url,
                    description=description,
                    engine=self.name,
                    position=i + 1,
                    timestamp=datetime.now().isoformat(),
                    html_structure={},
                    raw_html="",
                )
            )
        return results


def _unwrap_ddg_url(raw: str) -> str:
    """Resolve a DuckDuckGo result link to its real target URL.

    DDG HTML wraps every organic result in a redirect of the form
    `//duckduckgo.com/l/?uddg=<URL-encoded-target>&rut=...`. Sometimes
    the href is protocol-relative (`//…`), sometimes absolute
    (`https://…`). Either way the real URL is in `uddg`. We extract and
    URL-decode it, and add `https:` to protocol-relative non-redirect
    links as a fallback.
    """
    from urllib.parse import parse_qs, unquote, urlparse

    if not raw:
        return ""
    try:
        parsed = urlparse(raw if "://" in raw else "https:" + raw)
        if "duckduckgo.com" in (parsed.netloc or "") and parsed.query:
            q = parse_qs(parsed.query)
            if "uddg" in q and q["uddg"]:
                return unquote(q["uddg"][0])
    except Exception:
        pass
    # Not a DDG redirect - normalize protocol-relative refs.
    if raw.startswith("//"):
        return "https:" + raw
    return raw
