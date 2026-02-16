"""Module de parsing de documents PDF.

Supporte deux backends :
- pdfplumber : extraction mécanique (rapide, gratuit)
- yaml_template : extraction via templates YAML (configurable)

Le flux d'import unifié :
1. extract_eleve_name() - extrait le nom depuis le PDF (regex)
2. get_parser().parse() - extrait les données structurées du PDF original
3. _pseudonymize_extraction() - remplace les noms par eleve_id dans les textes
   (regex + NER safety net sur les appréciations)
"""

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from src.document.anonymizer import extract_eleve_name
from src.document.parser import PDFContent, clean_text, extract_pdf_content
from src.document.pdfplumber_parser import PdfplumberParser
from src.llm.config import settings

if TYPE_CHECKING:
    from src.core.models import EleveExtraction


class ParserType(Enum):
    """Types de parser PDF disponibles."""

    PDFPLUMBER = "pdfplumber"
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

    if parser_type == ParserType.YAML_TEMPLATE:
        from src.document.yaml_template_parser import YamlTemplateParser

        return YamlTemplateParser()

    return PdfplumberParser()


__all__ = [
    # Flux d'import
    "extract_eleve_name",
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


def __getattr__(name: str):
    """Lazy imports pour éviter le chargement des modèles au démarrage."""
    if name == "YamlTemplateParser":
        from src.document.yaml_template_parser import YamlTemplateParser

        return YamlTemplateParser
    if name == "generate_debug_pdf":
        from src.document.debug_visualizer import generate_debug_pdf

        return generate_debug_pdf
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
