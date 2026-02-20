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

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from src.document.anonymizer import extract_eleve_name
from src.document.parser import PDFContent, clean_text, extract_pdf_content

if TYPE_CHECKING:
    from src.core.models import EleveExtraction


class PDFParser(Protocol):
    """Interface commune pour les parsers PDF."""

    def parse(
        self,
        pdf_data: bytes | str | Path,
        eleve_id: str,
        genre: str | None = None,
    ) -> "EleveExtraction": ...


def get_parser() -> PDFParser:
    """Retourne le parser PDF (YamlTemplateParser).

    Returns:
        Instance du parser.
    """
    from src.document.yaml_template_parser import YamlTemplateParser

    return YamlTemplateParser()


__all__ = [
    # Flux d'import
    "extract_eleve_name",
    # Factory et types
    "get_parser",
    "PDFParser",
    # Parsers
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
