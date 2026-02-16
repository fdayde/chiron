"""Parser PDF template-driven via fichier YAML.

Charge les règles d'extraction depuis un template YAML et dispatch
vers les fonctions utilitaires existantes de pdfplumber_parser.
"""

import logging
import re
from pathlib import Path

import yaml

from src.core.models import EleveExtraction
from src.document.parser import extract_pdf_content
from src.document.pdfplumber_parser import (
    extract_key_value,
    extract_number,
    parse_engagements,
    parse_raw_tables,
)

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


class YamlTemplateParser:
    """Parser PDF configurable via template YAML."""

    def __init__(self, template_name: str = "pronote_standard"):
        template_path = TEMPLATES_DIR / f"{template_name}.yaml"
        if not template_path.exists():
            raise FileNotFoundError(f"Template introuvable: {template_path}")
        with open(template_path, encoding="utf-8") as f:
            self._config = yaml.safe_load(f)
        self._fields = self._config.get("fields", {})
        self._tables = self._config.get("tables", {})
        logger.info(
            "Template chargé: %s v%s",
            self._config["template"]["name"],
            self._config["template"]["version"],
        )

    def parse(
        self,
        pdf_path: str | Path,
        eleve_id: str,
        genre: str | None = None,
    ) -> EleveExtraction:
        """Parse un PDF anonymisé selon le template YAML.

        Args:
            pdf_path: Chemin vers le fichier PDF.
            eleve_id: Identifiant anonyme de l'élève.
            genre: Genre si connu (extrait en amont).

        Returns:
            EleveExtraction avec les données structurées.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        logger.info(
            "Parsing (yaml_template): %s (eleve_id=%s)", pdf_path.name, eleve_id
        )

        content = extract_pdf_content(pdf_path)
        if not content.tables and not content.text:
            return EleveExtraction(eleve_id=eleve_id, nom=None, prenom=None)

        raw_text = content.text or ""

        # --- Extraction des champs depuis le texte ---
        extracted = {}
        for field_name, spec in self._fields.items():
            extracted[field_name] = self._extract_field(raw_text, spec)

        # Genre: paramètre > extraction template
        if not genre:
            genre_raw = extracted.get("genre")
            if genre_raw:
                normalize = self._fields.get("genre", {}).get("normalize", {})
                genre = normalize.get(genre_raw.lower(), genre_raw)

        # Absences justifiées (bool)
        absences_justifiees = extracted.get("absences_justifiees")
        if isinstance(absences_justifiees, bool):
            pass  # already a bool from "contains" extract
        else:
            absences_justifiees = None

        # --- Extraction des tables ---
        matieres = parse_raw_tables(content.tables)

        return EleveExtraction(
            eleve_id=eleve_id,
            nom=None,
            prenom=None,
            genre=genre,
            absences_demi_journees=extracted.get("absences"),
            absences_justifiees=absences_justifiees,
            retards=extracted.get("retards"),
            engagements=extracted.get("engagements") or [],
            moyenne_generale=extracted.get("moyenne_generale"),
            annee_scolaire=extracted.get("annee_scolaire"),
            trimestre=extracted.get("trimestre"),
            matieres=matieres,
            raw_text=raw_text,
            raw_tables=content.tables,
        )

    def _extract_field(self, text: str, spec: dict):
        """Dispatch l'extraction d'un champ selon sa spec YAML."""
        method = spec.get("method")

        if method == "key_value":
            return self._extract_key_value_field(text, spec)
        if method == "regex":
            return self._extract_regex_field(text, spec)

        logger.warning("Méthode d'extraction inconnue: %s", method)
        return None

    def _extract_key_value_field(self, text: str, spec: dict):
        """Extrait un champ via key_value + post-traitement."""
        raw = extract_key_value(text, spec["key"])
        extract = spec.get("extract")

        if extract == "number":
            value = extract_number(raw)
            if spec.get("cast") == "int" and value is not None:
                return int(value)
            return value

        if extract == "contains":
            keyword = spec.get("contains", "")
            return bool(raw and keyword.lower() in raw.lower())

        if extract == "engagements":
            return parse_engagements(raw)

        # Pas d'extract → retourner la valeur brute
        return raw

    def _extract_regex_field(self, text: str, spec: dict):
        """Extrait un champ via regex directe sur le texte."""
        pattern = spec.get("pattern", "")
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return None
        value = match.group(1)
        if spec.get("cast") == "int":
            try:
                return int(value.strip())
            except ValueError:
                return None
        return value.strip()
