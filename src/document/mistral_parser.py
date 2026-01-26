"""Parser PDF utilisant Mistral OCR (API cloud).

Extraction via vision model - interprète la structure sémantique.
Intègre l'anonymisation automatique avant envoi cloud.
"""

import base64
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from mistralai import Mistral

from src.core.models import EleveExtraction
from src.document.anonymizer import AnonymizationResult, get_anonymizer
from src.llm.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """Résultat du parsing avec métadonnées."""

    eleve: EleveExtraction
    """Données de l'élève extraites."""

    anonymization: AnonymizationResult | None
    """Résultat de l'anonymisation (None si désactivée)."""

    ocr_metadata: dict
    """Métadonnées OCR (provider, model, cost, duration)."""


class MistralOCRParser:
    """Parser PDF utilisant l'API Mistral OCR avec anonymisation intégrée.

    Par défaut, anonymise le PDF avant envoi pour garantir RGPD.
    """

    def __init__(self, anonymize: bool = True):
        """Initialise le parser Mistral OCR.

        Args:
            anonymize: Si True, anonymise le PDF avant envoi cloud.
        """
        if not settings.mistral_ocr_api_key:
            raise ValueError("MISTRAL_OCR_API_KEY non configurée dans .env")

        self._client = Mistral(api_key=settings.mistral_ocr_api_key)
        self._model = settings.mistral_ocr_model
        self._anonymize = anonymize
        self._anonymizer = get_anonymizer() if anonymize else None

    def parse(
        self,
        pdf_path: str | Path,
        eleve_id: str | None = None,
        classe_id: str | None = None,
    ) -> list[EleveExtraction]:
        """Parse PDF via Mistral OCR et retourne les données extraites.

        Si anonymize=True (défaut), le PDF est anonymisé avant envoi cloud.

        Args:
            pdf_path: Chemin vers le fichier PDF.
            eleve_id: ID anonyme à utiliser. Si None, génère automatiquement.
            classe_id: ID de classe pour le préfixe de l'eleve_id.

        Returns:
            Liste avec un EleveExtraction contenant les données.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        logger.info(f"Parsing avec Mistral OCR: {pdf_path.name}")

        # Générer eleve_id si non fourni
        if eleve_id is None:
            eleve_id = self._generate_eleve_id(classe_id)

        # Anonymiser si activé
        anonymization_result = None
        pdf_bytes = None

        if self._anonymize and self._anonymizer:
            try:
                logger.info("Anonymisation du PDF avant envoi cloud...")
                anonymization_result = self._anonymizer.anonymize(pdf_path, eleve_id)
                pdf_bytes = anonymization_result.pdf_bytes
                logger.info(
                    f"Anonymisation OK: {anonymization_result.replacements_count} remplacements"
                )
            except Exception as e:
                logger.warning(f"Échec anonymisation: {e}. Envoi du PDF original.")
                pdf_bytes = None

        # Si pas de bytes anonymisés, utiliser le fichier original
        if pdf_bytes is None:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()

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

        # Extraire le markdown de toutes les pages
        response_dict = json.loads(response.model_dump_json())
        markdown_pages = [
            page.get("markdown", "") for page in response_dict.get("pages", [])
        ]
        full_markdown = "\n\n".join(markdown_pages)

        if not full_markdown.strip():
            return []

        # Construire le résultat
        identity = anonymization_result.identity if anonymization_result else {}

        eleve = EleveExtraction(
            eleve_id=eleve_id,
            nom=None,  # Jamais stocké dans chiron.duckdb
            prenom=None,  # Jamais stocké
            genre=identity.get("genre"),
            etablissement=identity.get("etablissement"),
            raw_text=full_markdown,
            raw_tables=[],
        )

        # Stocker les métadonnées OCR dans un attribut temporaire
        # (sera utilisé par le repository pour le stockage)
        eleve._ocr_metadata = {
            "provider": "mistral",
            "model": self._model,
            "duration_ms": duration_ms,
            "anonymized": self._anonymize and anonymization_result is not None,
            "replacements_count": (
                anonymization_result.replacements_count if anonymization_result else 0
            ),
        }

        # Stocker l'identité pour le mapping (sera utilisé par le repository)
        eleve._identity = identity if anonymization_result else None

        return [eleve]

    def parse_with_details(
        self,
        pdf_path: str | Path,
        eleve_id: str | None = None,
        classe_id: str | None = None,
    ) -> ParseResult:
        """Parse PDF et retourne le résultat détaillé avec métadonnées.

        Args:
            pdf_path: Chemin vers le fichier PDF.
            eleve_id: ID anonyme à utiliser.
            classe_id: ID de classe.

        Returns:
            ParseResult avec eleve, anonymization et ocr_metadata.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        if eleve_id is None:
            eleve_id = self._generate_eleve_id(classe_id)

        # Anonymiser
        anonymization_result = None
        pdf_bytes = None

        if self._anonymize and self._anonymizer:
            try:
                anonymization_result = self._anonymizer.anonymize(pdf_path, eleve_id)
                pdf_bytes = anonymization_result.pdf_bytes
            except Exception as e:
                logger.warning(f"Échec anonymisation: {e}")

        if pdf_bytes is None:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()

        # OCR
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

        response_dict = json.loads(response.model_dump_json())
        markdown_pages = [
            page.get("markdown", "") for page in response_dict.get("pages", [])
        ]
        full_markdown = "\n\n".join(markdown_pages)

        identity = anonymization_result.identity if anonymization_result else {}

        eleve = EleveExtraction(
            eleve_id=eleve_id,
            nom=None,
            prenom=None,
            genre=identity.get("genre"),
            etablissement=identity.get("etablissement"),
            raw_text=full_markdown,
            raw_tables=[],
        )

        ocr_metadata = {
            "provider": "mistral",
            "model": self._model,
            "duration_ms": duration_ms,
            "anonymized": anonymization_result is not None,
        }

        return ParseResult(
            eleve=eleve,
            anonymization=anonymization_result,
            ocr_metadata=ocr_metadata,
        )

    def _generate_eleve_id(self, classe_id: str | None = None) -> str:
        """Génère un ID élève unique."""
        import uuid

        prefix = "ELEVE"
        if classe_id:
            # Format: ELEVE_3A_001 (avec classe)
            short_id = str(uuid.uuid4())[:8].upper()
            return f"{prefix}_{classe_id}_{short_id}"
        else:
            # Format: ELEVE_ABC12345
            short_id = str(uuid.uuid4())[:8].upper()
            return f"{prefix}_{short_id}"

    def _encode_pdf(self, pdf_path: Path) -> str:
        """Encode un PDF en base64."""
        with open(pdf_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
