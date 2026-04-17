#!/usr/bin/env python3
"""
Unified content extractors for RivalSearchMCP.
Consolidates the best extraction methods from all modules.
"""

import re
from abc import ABC, abstractmethod
from typing import Any

from bs4 import BeautifulSoup, Tag

from src.logging.logger import logger

# Performance optimization imports
try:
    from selectolax.parser import HTMLParser

    SELECTOLAX_AVAILABLE = True
except ImportError:
    SELECTOLAX_AVAILABLE = False

try:
    import importlib.util

    LXML_AVAILABLE = importlib.util.find_spec("lxml") is not None
except Exception:
    LXML_AVAILABLE = False


class BaseContentExtractor(ABC):
    """Base class for content extractors."""

    def __init__(self):
        """Initialize the extractor."""
        pass

    @abstractmethod
    def extract(self, content: str, **kwargs) -> Any:
        """Extract content using the extractor's method."""
        pass


class UnifiedContentExtractor(BaseContentExtractor):
    """Unified content extractor with multiple fallback methods."""

    def extract(self, html_content: str, **kwargs) -> str:
        """Extract main content from HTML using multiple optimized methods as fallbacks."""
        if not html_content:
            return ""

        try:
            # Method 1: Use selectolax for ultra-fast parsing (if available)
            if SELECTOLAX_AVAILABLE:
                try:
                    parser = HTMLParser(html_content)

                    # Try multiple content selectors with selectolax
                    content_selectors = [
                        "main",
                        '[role="main"]',
                        ".main-content",
                        ".content",
                        ".post-content",
                        ".article-content",
                        "#content",
                        "#main",
                        ".entry-content",
                        ".post-body",
                        ".article-body",
                    ]

                    for selector in content_selectors:
                        try:
                            element = parser.css_first(selector)
                            if element:
                                content = element.text(separator=" ", strip=True)
                                if len(content) > 100:
                                    logger.debug(f"Method 1 (selectolax {selector}) succeeded")
                                    return content
                        except Exception:
                            continue

                    # Try body extraction with selectolax
                    try:
                        body = parser.css_first("body")
                        if body:
                            content = body.text(separator=" ", strip=True)
                            if len(content) > 100:
                                logger.debug("Method 1 (selectolax body) succeeded")
                                return content
                    except Exception:
                        pass

                except Exception as e:
                    logger.debug(f"selectolax method failed: {e}")

            # Method 2: Use BeautifulSoup with lxml parser (faster than html.parser)
            parser_name = "lxml" if LXML_AVAILABLE else "html.parser"
            soup = BeautifulSoup(html_content, parser_name)

            # Try multiple content selectors
            content_selectors = [
                "main",
                '[role="main"]',
                ".main-content",
                ".content",
                ".post-content",
                ".article-content",
                "#content",
                "#main",
                ".entry-content",
                ".post-body",
                ".article-body",
            ]

            for selector in content_selectors:
                try:
                    element = soup.select_one(selector)
                    if element and hasattr(element, "get_text"):
                        content = element.get_text(separator=" ", strip=True)
                        if len(content) > 100:
                            logger.debug(f"Method 2 (BeautifulSoup {selector}) succeeded")
                            return content
                except Exception:
                    continue

            # Method 3: Extract from body with cleanup
            try:
                # Remove unwanted elements
                for tag in soup(["script", "style", "nav", "footer", "header", "aside", "menu"]):
                    if isinstance(tag, Tag) and hasattr(tag, "decompose"):
                        tag.decompose()

                body = soup.find("body")
                if isinstance(body, Tag) and hasattr(body, "get_text"):
                    content = body.get_text(separator=" ", strip=True)
                    if len(content) > 100:
                        logger.debug("Method 3 (body cleanup) succeeded")
                        return content
            except Exception:
                pass

            # Method 4: Fallback to regex-based extraction
            try:
                # Remove HTML tags and clean up
                text_content = re.sub(r"<[^>]+>", "", html_content)
                text_content = re.sub(r"\s+", " ", text_content)
                text_content = text_content.strip()

                if len(text_content) > 100:
                    logger.debug("Method 4 (regex) succeeded")
                    return text_content
            except Exception:
                pass

            # Method 5: Last resort - extract from title and any text
            try:
                title = soup.find("title")
                if isinstance(title, Tag) and hasattr(title, "get_text"):
                    title_text = title.get_text()
                    if len(title_text) > 10:
                        logger.debug("Method 5 (title) succeeded")
                        return title_text
            except Exception:
                pass

            logger.warning("All content extraction methods failed")
            return ""

        except Exception as e:
            logger.error(f"Content extraction failed: {e}")
            return ""
