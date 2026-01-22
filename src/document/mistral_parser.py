"""Parser PDF utilisant Mistral OCR (API cloud).

Extraction via vision model - interprète la structure sémantique.
"""

import base64
import json
import logging
from pathlib import Path

from mistralai import Mistral

from src.core.models import EleveExtraction
from src.llm.config import settings

logger = logging.getLogger(__name__)


class MistralOCRParser:
    """Parser PDF utilisant l'API Mistral OCR."""

    def __init__(self):
        """Initialise le client Mistral."""
        if not settings.mistral_ocr_api_key:
            raise ValueError("MISTRAL_OCR_API_KEY non configurée dans .env")
        self._client = Mistral(api_key=settings.mistral_ocr_api_key)
        self._model = settings.mistral_ocr_model

    def parse(self, pdf_path: str | Path) -> list[EleveExtraction]:
        """Parse PDF via Mistral OCR et retourne les données brutes.

        Args:
            pdf_path: Chemin vers le fichier PDF.

        Returns:
            Liste avec un EleveExtraction contenant raw_text (markdown).
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        logger.info(f"Parsing with Mistral OCR: {pdf_path.name}")

        # Encoder le PDF en base64
        base64_pdf = self._encode_pdf(pdf_path)

        # Appeler l'API OCR
        response = self._client.ocr.process(
            model=self._model,
            document={
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{base64_pdf}",
            },
            include_image_base64=True,
        )

        # Extraire le markdown de toutes les pages
        response_dict = json.loads(response.model_dump_json())
        markdown_pages = [
            page.get("markdown", "") for page in response_dict.get("pages", [])
        ]
        full_markdown = "\n\n".join(markdown_pages)

        if not full_markdown.strip():
            return []

        return [
            EleveExtraction(
                raw_text=full_markdown,
                raw_tables=[],  # Mistral retourne du markdown, pas de tables structurées
            )
        ]

    def _encode_pdf(self, pdf_path: Path) -> str:
        """Encode un PDF en base64."""
        with open(pdf_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
