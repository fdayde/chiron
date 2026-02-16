"""Module de parsing de documents PDF.

Supporte deux backends :
- pdfplumber : extraction mécanique (rapide, gratuit)
- mistral_ocr : vision model cloud (précis, payant)

Le flux d'import unifié :
1. extract_eleve_name() - extrait le nom depuis le PDF
2. anonymize_pdf() - remplace les noms par l'eleve_id
3. get_parser().parse() - extrait les données structurées

Usage:
    from src.document import (
        extract_eleve_name,
        anonymize_pdf,
        get_parser,
        ParserType,
    )

    # 1. Extraire le nom
    identity = extract_eleve_name(pdf_path)
    # {"nom": "Dupont", "prenom": "Marie", "genre": "Fille"}

    # 2. Anonymiser (après avoir créé l'eleve_id via pseudonymizer)
    pdf_bytes = anonymize_pdf(pdf_path, eleve_id)

    # 3. Parser
    parser = get_parser()  # ou get_parser(ParserType.MISTRAL_OCR)
    eleve = parser.parse(pdf_bytes, eleve_id, genre=identity.get("genre"))
"""

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from src.document.anonymizer import anonymize_pdf, extract_eleve_name
from src.document.parser import PDFContent, clean_text, extract_pdf_content
from src.document.pdfplumber_parser import PdfplumberParser
from src.llm.config import settings

if TYPE_CHECKING:
    from src.core.models import EleveExtraction


class ParserType(Enum):
    """Types de parser PDF disponibles."""

    PDFPLUMBER = "pdfplumber"
    MISTRAL_OCR = "mistral_ocr"
    YAML_TEMPLATE = "yaml_template"


class PDFParser(Protocol):
    """Interface commune pour les parsers PDF."""

    def parse(
        self,
        pdf_data: bytes | str | Path,
        eleve_id: str,
        genre: str | None = None,
    ) -> "EleveExtraction": ...


def get_parser(parser_type: ParserType | None = None) -> PDFParser:
    """Factory pour obtenir le parser PDF configuré.

    Args:
        parser_type: Type de parser. Si None, utilise PDF_PARSER_TYPE de .env.

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

    if parser_type == ParserType.YAML_TEMPLATE:
        from src.document.yaml_template_parser import YamlTemplateParser

        return YamlTemplateParser()

    return PdfplumberParser()


__all__ = [
    # Flux d'import
    "extract_eleve_name",
    "anonymize_pdf",
    # Factory et types
    "get_parser",
    "ParserType",
    "PDFParser",
    # Parsers
    "PdfplumberParser",
    "YamlTemplateParser",
    # Debug
    "generate_debug_pdf",
    # Utilitaires
    "PDFContent",
    "extract_pdf_content",
    "clean_text",
]


# Lazy import pour MistralOCRParser
def __getattr__(name: str):
    """Lazy imports pour éviter le chargement des modèles au démarrage."""
    if name == "MistralOCRParser":
        from src.document.mistral_parser import MistralOCRParser

        return MistralOCRParser
    if name == "YamlTemplateParser":
        from src.document.yaml_template_parser import YamlTemplateParser

        return YamlTemplateParser
    if name == "generate_debug_pdf":
        from src.document.debug_visualizer import generate_debug_pdf

        return generate_debug_pdf
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
