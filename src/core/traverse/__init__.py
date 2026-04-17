"""
Website traversal. The `map_website` MCP tool (src/tools/traversal.py)
uses the three specialised entry points below; `WebsiteTraverser` is
re-exported for internal use by the specialised helpers.

The previous convenience layer (`traverse_website`, `get_sitemap`,
`extract_links`, `analyze_structure`) was never called by any tool or
test and has been removed as dead code.
"""

from .core import WebsiteTraverser
from .specialized import explore_documentation, map_website_structure, research_topic

__all__ = [
    "WebsiteTraverser",
    "research_topic",
    "explore_documentation",
    "map_website_structure",
]
