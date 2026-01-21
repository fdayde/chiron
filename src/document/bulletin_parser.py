"""Minimal parser for PDF using pdfplumber.

Returns raw data only - no interpretation.
"""

import logging
from pathlib import Path

from src.core.models import EleveExtraction
from src.document.parser import extract_pdf_content

logger = logging.getLogger(__name__)


class BulletinParser:
    """Minimal PDF parser - returns raw tables and text."""

    def parse(self, pdf_path: str | Path) -> list[EleveExtraction]:
        """Parse PDF and return raw data.

        Args:
            pdf_path: Path to PDF file.

        Returns:
            List with one EleveExtraction containing raw_text and raw_tables.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        logger.info(f"Parsing: {pdf_path.name}")

        content = extract_pdf_content(pdf_path)

        if not content.tables and not content.text:
            return []

        # Return raw data only - no interpretation
        return [
            EleveExtraction(
                raw_text=content.text,
                raw_tables=content.tables,
            )
        ]
