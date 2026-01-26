"""Module de parsing de documents PDF.

Supporte deux backends :
- pdfplumber : extraction mécanique (rapide, gratuit)
- mistral_ocr : vision model cloud (précis, payant) + anonymisation automatique

Usage:
    from src.document import get_parser, ParserType, estimate_mistral_cost

    # Utiliser le parser configuré dans .env (PDF_PARSER_TYPE)
    parser = get_parser()
    result = parser.parse("bulletin.pdf")

    # Ou forcer un parser spécifique avec anonymisation (défaut)
    parser = get_parser(ParserType.MISTRAL_OCR)
    result = parser.parse("bulletin.pdf", eleve_id="ELEVE_001")

    # Estimer le coût avant envoi Mistral
    estimate = estimate_mistral_cost([Path("a.pdf"), Path("b.pdf")])
    print(f"{estimate['pages']} pages -> ${estimate['cost_usd']}")

    # Utiliser l'anonymizer directement
    from src.document import PDFAnonymizer
    anonymizer = PDFAnonymizer()
    result = anonymizer.anonymize(pdf_path, "ELEVE_001")
"""

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import pdfplumber

from src.document.parser import PDFContent, clean_text, extract_pdf_content
from src.document.pdfplumber_parser import PdfplumberParser
from src.llm.config import settings

if TYPE_CHECKING:
    from src.core.models import EleveExtraction


class ParserType(Enum):
    """Types de parser PDF disponibles."""

    PDFPLUMBER = "pdfplumber"
    MISTRAL_OCR = "mistral_ocr"


class PDFParser(Protocol):
    """Interface commune pour les parsers PDF."""

    def parse(self, pdf_path: str | Path) -> list["EleveExtraction"]: ...


def get_parser(parser_type: ParserType | None = None) -> PDFParser:
    """Factory pour obtenir le parser PDF configuré.

    Args:
        parser_type: Type de parser à utiliser. Si None, utilise PDF_PARSER_TYPE de .env.

    Returns:
        Instance du parser demandé.

    Raises:
        ValueError: Si le type de parser est invalide.
    """
    if parser_type is None:
        # Lire depuis la config
        type_str = settings.pdf_parser_type.lower()
        try:
            parser_type = ParserType(type_str)
        except ValueError as e:
            raise ValueError(
                f"PDF_PARSER_TYPE invalide: {type_str}. "
                f"Valeurs possibles: {[p.value for p in ParserType]}"
            ) from e

    if parser_type == ParserType.MISTRAL_OCR:
        from src.document.mistral_parser import MistralOCRParser

        return MistralOCRParser()

    return PdfplumberParser()


def count_pdf_pages(pdf_path: str | Path) -> int:
    """Compte le nombre de pages d'un PDF.

    Args:
        pdf_path: Chemin vers le fichier PDF.

    Returns:
        Nombre de pages.
    """
    with pdfplumber.open(pdf_path) as pdf:
        return len(pdf.pages)


def estimate_mistral_cost(
    pdf_paths: list[Path] | list[str],
    cost_per_1000_pages: float | None = None,
) -> dict:
    """Estime le coût Mistral OCR pour une liste de PDFs.

    Args:
        pdf_paths: Liste des chemins vers les fichiers PDF.
        cost_per_1000_pages: Coût en USD pour 1000 pages.
            Si None, utilise MISTRAL_OCR_COST_PER_1000_PAGES de .env.

    Returns:
        Dict avec 'pages' (total) et 'cost_usd' (estimation).
    """
    if cost_per_1000_pages is None:
        cost_per_1000_pages = settings.mistral_ocr_cost_per_1000_pages

    total_pages = sum(count_pdf_pages(p) for p in pdf_paths)

    return {
        "pages": total_pages,
        "cost_usd": round(total_pages / 1000 * cost_per_1000_pages, 4),
    }


__all__ = [
    # Factory et types
    "get_parser",
    "ParserType",
    "PDFParser",
    # Parsers
    "PdfplumberParser",
    "MistralOCRParser",
    # Anonymisation
    "PDFAnonymizer",
    "AnonymizationResult",
    "get_anonymizer",
    # Utilitaires
    "PDFContent",
    "extract_pdf_content",
    "clean_text",
    "count_pdf_pages",
    "estimate_mistral_cost",
]


# Imports pour les exports
def __getattr__(name: str):
    """Lazy imports pour éviter le chargement des modèles au démarrage."""
    if name == "MistralOCRParser":
        from src.document.mistral_parser import MistralOCRParser

        return MistralOCRParser
    if name == "PDFAnonymizer":
        from src.document.anonymizer import PDFAnonymizer

        return PDFAnonymizer
    if name == "AnonymizationResult":
        from src.document.anonymizer import AnonymizationResult

        return AnonymizationResult
    if name == "get_anonymizer":
        from src.document.anonymizer import get_anonymizer

        return get_anonymizer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
