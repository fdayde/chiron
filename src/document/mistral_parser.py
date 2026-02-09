"""Parser PDF utilisant Mistral OCR (API cloud).

Extrait les données structurées via le modèle de vision Mistral.
Le PDF doit être anonymisé AVANT l'envoi (fait en amont par le flux d'import).
"""

import base64
import json
import logging
import time
from pathlib import Path

from mistralai import Mistral

from src.core.models import EleveExtraction
from src.llm.config import settings

logger = logging.getLogger(__name__)


class MistralOCRParser:
    """Parser PDF utilisant l'API Mistral OCR.

    Attend un PDF déjà anonymisé (RGPD compliance).
    """

    def __init__(self):
        """Initialise le parser Mistral OCR."""
        if not settings.mistral_ocr_api_key:
            raise ValueError("MISTRAL_OCR_API_KEY non configurée dans .env")

        self._client = Mistral(api_key=settings.mistral_ocr_api_key)
        self._model = settings.mistral_ocr_model

    def parse(
        self,
        pdf_data: bytes | str | Path,
        eleve_id: str,
        genre: str | None = None,
    ) -> EleveExtraction:
        """Parse un PDF anonymisé via Mistral OCR.

        Args:
            pdf_data: PDF anonymisé (bytes, chemin fichier, ou Path).
            eleve_id: Identifiant de l'élève (fourni par le flux d'import).
            genre: Genre de l'élève si connu (extrait en amont).

        Returns:
            EleveExtraction avec les données extraites, nom=None.
        """
        # Convertir en bytes si nécessaire
        if isinstance(pdf_data, str | Path):
            pdf_path = Path(pdf_data)
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF not found: {pdf_path}")
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
        else:
            pdf_bytes = pdf_data

        logger.info(f"Parsing avec Mistral OCR (eleve_id={eleve_id})")

        # Appeler l'API OCR
        start_time = time.perf_counter()
        base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

        response = self._client.ocr.process(
            model=self._model,
            document={
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{base64_pdf}",
            },
            include_image_base64=False,
        )

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(f"Mistral OCR terminé en {duration_ms}ms")

        # Extraire le markdown de toutes les pages
        response_dict = json.loads(response.model_dump_json())
        markdown_pages = [
            page.get("markdown", "") for page in response_dict.get("pages", [])
        ]
        full_markdown = "\n\n".join(markdown_pages)

        if not full_markdown.strip():
            logger.warning("Mistral OCR a retourné un contenu vide")
            return EleveExtraction(eleve_id=eleve_id, nom=None, prenom=None)

        return EleveExtraction(
            eleve_id=eleve_id,
            nom=None,  # Anonymisé
            prenom=None,  # Anonymisé
            genre=genre,
            raw_text=full_markdown,
            raw_tables=[],
        )
