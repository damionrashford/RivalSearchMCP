"""
Multi-search engine core module for RivalSearchMCP.
Provides optimized search across multiple engines with concurrent processing.
"""

import asyncio
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urljoin, urlparse

from scrapling.parser import Selector

from rival_search_mcp.logging.logger import logger


class MultiSearchResult:
    """Represents a search result from any engine."""

    def __init__(
        self,
        title: str,
        url: str,
        description: str,
        engine: str,
        position: int,
        timestamp: str,
        real_url: Optional[str] = None,
        full_content: Optional[str] = None,
        internal_links: Optional[List[str]] = None,
        second_level_content: Optional[Dict[str, Any]] = None,
    ):
        self.title = title
        self.url = url
        self.description = description
        self.engine = engine
        self.position = position
        self.timestamp = timestamp
        self.real_url = real_url
        self.full_content = full_content
        self.internal_links = internal_links
        self.second_level_content = second_level_content

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "url": self.url,
            "description": self.description,
            "engine": self.engine,
            "position": self.position,
            "timestamp": self.timestamp,
            "real_url": self.real_url,
            "full_content": self.full_content,
            "internal_links": self.internal_links,
            "second_level_content": self.second_level_content,
        }


class BaseSearchEngine:
    """Base class for search engines with optimized content extraction."""

    def __init__(self, name: str, base_url: str):

        self.name = name
        self.base_url = base_url
        self.visited_urls: Set[str] = set()

    def is_configured(self) -> bool:
        """Whether this engine should participate in the search pool."""
        return True

    async def search(
        self,
        query: str,
        num_results: int = 10,
        extract_content: bool = True,
        follow_links: bool = True,
        max_depth: int = 2,
    ) -> List[MultiSearchResult]:
        """Search using the engine's implementation."""
        raise NotImplementedError

    async def _fetch_page_content(self, url: str) -> Optional[str]:
        """Fetch page content. Uses Scrapling's TLS fingerprinting so
        Cloudflare-fronted result pages return 200 instead of 403."""
        if url in self.visited_urls:
            return None

        self.visited_urls.add(url)

        from rival_search_mcp.utils.scrapling_client import fetch_html

        return await fetch_html(url)

    def _extract_real_url(self, url: str) -> Optional[str]:
        """Unwrap common search-engine redirect links to their target URL."""
        try:
            if "duckduckgo.com" in url and "uddg=" in url:
                parsed = urlparse(url)
                query_params = parse_qs(parsed.query)
                if "uddg" in query_params:
                    return query_params["uddg"][0]

            if "redirect" in url.lower() or "go" in url.lower():
                parsed = urlparse(url)
                query_params = parse_qs(parsed.query)

                for param in ["url", "target", "link", "dest", "to"]:
                    if param in query_params:
                        return query_params[param][0]

            return url
        except Exception as e:
            logger.debug(f"Failed to extract real URL from redirect: {e}")
            return url

    def _extract_main_content(self, html_content: str) -> str:
        """Extract main content from HTML using unified content extractor."""
        from rival_search_mcp.core.content.extractors import UnifiedContentExtractor

        extractor = UnifiedContentExtractor()
        return extractor.extract(html_content)

    def _extract_internal_links(self, html_content: str, base_url: str) -> List[str]:
        """Extract same-domain links via Scrapling's Selector."""
        try:
            sel = Selector(content=html_content)
            seen: Set[str] = set()
            for a_el in sel.css("a[href]"):
                href = a_el.attrib.get("href", "")
                if not href:
                    continue
                absolute_url = urljoin(base_url, href)
                if self._extract_domain(absolute_url) == self._extract_domain(base_url):
                    seen.add(absolute_url)
            unique_links = list(seen)[:10]
            logger.info(f"Extracted {len(unique_links)} internal links from {base_url}")
            return unique_links
        except Exception as e:
            logger.warning(f"Failed to extract internal links: {e}")
            return []

    async def _extract_second_level_content(
        self, url: str, internal_links: List[str], max_links: int = 3
    ) -> Dict[str, Any]:
        """Extract content from internal links (second level) using concurrent processing."""
        second_level = {}

        async def process_second_level_link(link: str) -> Tuple[str, Dict[str, Any]]:
            try:
                logger.info(f"Extracting second level content from: {link}")
                content = await self._fetch_page_content(link)

                if not content:
                    return link, {}

                main_content = self._extract_main_content(content)
                internal_links = self._extract_internal_links(content, link)

                result = {
                    "title": self._extract_title(content),
                    "content_preview": (
                        main_content[:500] + "..." if len(main_content) > 500 else main_content
                    ),
                    "content_length": len(main_content),
                    "internal_links": internal_links,
                }

                if internal_links:
                    third_level = await self._extract_third_level_content_concurrent(
                        internal_links[:2]
                    )
                    result["third_level"] = third_level

                return link, result

            except Exception as e:
                logger.warning(f"Failed to extract second level from {link}: {e}")
                return link, {}

        tasks = [process_second_level_link(link) for link in internal_links[:max_links]]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, tuple) and len(result) == 2:
                link, result_data = result
                if isinstance(result_data, dict) and result_data:
                    second_level[link] = result_data

        return second_level

    async def _extract_third_level_content_concurrent(
        self, third_links: List[str]
    ) -> Dict[str, Any]:
        """Extract third level content concurrently for better performance."""
        third_level = {}

        async def process_third_level_link(link: str) -> Tuple[str, Dict[str, Any]]:
            try:
                third_content = await self._fetch_page_content(link)
                if not third_content:
                    return link, {}

                third_main = self._extract_main_content(third_content)
                return link, {
                    "title": self._extract_title(third_content),
                    "content_preview": (
                        third_main[:300] + "..." if len(third_main) > 300 else third_main
                    ),
                    "content_length": len(third_main),
                }
            except Exception as e:
                logger.debug(f"Failed to extract third level from {link}: {e}")
                return link, {}

        tasks = [process_third_level_link(link) for link in third_links]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, tuple) and len(result) == 2:
                link, result_data = result
                if isinstance(result_data, dict) and result_data:
                    third_level[link] = result_data

        return third_level

    def _extract_title(self, html_content: str) -> str:
        """Extract page title from HTML."""
        try:
            el = Selector(content=html_content).css_first("title")
            return el.get_all_text(strip=True) if el else ""
        except Exception:
            return ""

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            return urlparse(url).netloc
        except Exception:
            return ""

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        if not text:
            return ""
        return re.sub(r"\s+", " ", text).strip()

    async def close(self):
        pass
