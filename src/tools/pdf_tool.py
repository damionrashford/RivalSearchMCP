"""
Document analysis tools for FastMCP server.
Extracts text and metadata from multiple document types.
"""

from fastmcp import FastMCP

from src.core.pdf import DocumentAnalyzer
from src.logging.logger import logger
from src.utils.markdown_formatter import format_document_markdown


def register_pdf_tools(mcp: FastMCP):
    """Register document analysis tools."""

    analyzer = DocumentAnalyzer()

    @mcp.tool(
        annotations={
            "title": "Document Analysis",
            "readOnlyHint": True,
            "openWorldHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
        # Large PDFs with OCR can take a while.
        timeout=180.0,
    )
    async def document_analysis(
        url: str, max_pages: int = 10, extract_metadata: bool = True, summary_length: int = 500
    ) -> str:
        """
        Download and analyze documents of multiple types with OCR support.

        Supports: PDF, Word (.docx), Text (.txt, .md), Images (.jpg, .png) with OCR.
        Extracts text content and metadata without requiring authentication.
        Automatically uses OCR for scanned PDFs and images.

        Args:
            url: URL of the document to analyze (PDF, Word, Text, etc.)
            max_pages: Maximum pages to extract (for PDFs, default: 10)
            extract_metadata: Whether to extract document metadata
            summary_length: Length of text preview in output (default: 500)
        """
        try:
            logger.info(f"Document analysis for: {url}")

            result = await analyzer.analyze_document(
                url=url, max_pages=max_pages, extract_metadata=extract_metadata
            )

            return format_document_markdown(result, summary_length)

        except Exception as e:
            logger.error(f"Document analysis failed: {e}")
            return f"# 📄 Document Analysis\n\n❌ **Error:** {str(e)}"
