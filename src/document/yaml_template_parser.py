"""Parser PDF template-driven via fichier YAML.

Charge les regles d'extraction depuis un template YAML et dispatch
vers les fonctions utilitaires de parser.py.

Supporte le format PRONOTE reel (v2.0) :
- Prof dans la colonne 0 de la table (sous le nom de la matiere)
- Notes Ecrit/Oral separees
- Footer avec absences, retards, appreciation globale
"""

import logging
import re
from pathlib import Path

import yaml

from src.core.models import EleveExtraction, MatiereExtraction
from src.document.parser import (
    extract_key_value,
    extract_number,
    extract_pdf_content,
    parse_engagements,
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
            "Template charge: %s v%s",
            self._config["template"]["name"],
            self._config["template"]["version"],
        )

    def parse(
        self,
        pdf_path: str | Path,
        eleve_id: str,
        genre: str | None = None,
    ) -> EleveExtraction:
        """Parse un PDF anonymise selon le template YAML.

        Args:
            pdf_path: Chemin vers le fichier PDF.
            eleve_id: Identifiant anonyme de l'eleve.
            genre: Genre si connu (extrait en amont).

        Returns:
            EleveExtraction avec les donnees structurees.
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

        # Genre: parametre > extraction template
        if not genre:
            genre_raw = extracted.get("genre")
            if genre_raw:
                normalize = self._fields.get("genre", {}).get("normalize", {})
                genre = normalize.get(genre_raw.lower(), genre_raw)

        # Absences justifiees (bool)
        absences_justifiees = extracted.get("absences_justifiees")
        if not isinstance(absences_justifiees, bool):
            absences_justifiees = None

        # --- Extraction des tables (PRONOTE) ---
        matieres, footer_data = self._parse_pronote_tables(content.tables)

        # Fusionner footer avec les champs texte (footer prioritaire si present)
        absences = footer_data.get("absences") or extracted.get("absences")
        retards = footer_data.get("retards") or extracted.get("retards")
        if footer_data.get("absences_justifiees") is not None:
            absences_justifiees = footer_data["absences_justifiees"]

        return EleveExtraction(
            eleve_id=eleve_id,
            nom=None,
            prenom=None,
            genre=genre,
            classe=extracted.get("classe"),
            trimestre=extracted.get("trimestre"),
            annee_scolaire=extracted.get("annee_scolaire"),
            absences_demi_journees=absences,
            absences_justifiees=absences_justifiees,
            retards=retards,
            engagements=extracted.get("engagements") or [],
            moyenne_generale=extracted.get("moyenne_generale"),
            matieres=matieres,
            raw_text=raw_text,
            raw_tables=content.tables,
        )

    # ------------------------------------------------------------------
    # Extraction des champs texte
    # ------------------------------------------------------------------

    def _extract_field(self, text: str, spec: dict):
        """Dispatch l'extraction d'un champ selon sa spec YAML."""
        method = spec.get("method")

        if method == "key_value":
            return self._extract_key_value_field(text, spec)
        if method == "regex":
            return self._extract_regex_field(text, spec)

        logger.warning("Methode d'extraction inconnue: %s", method)
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

        # Pas d'extract -> retourner la valeur brute
        return raw

    def _extract_regex_field(self, text: str, spec: dict):
        """Extrait un champ via regex directe sur le texte."""
        pattern = spec.get("pattern", "")
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if not match:
            return None
        value = match.group(1)
        if spec.get("cast") == "int":
            try:
                return int(value.strip())
            except ValueError:
                return None
        return value.strip()

    # ------------------------------------------------------------------
    # Extraction des tables PRONOTE
    # ------------------------------------------------------------------

    def _parse_pronote_tables(
        self, tables: list
    ) -> tuple[list[MatiereExtraction], dict]:
        """Parse les tables PRONOTE en matieres + donnees footer.

        Args:
            tables: Tables brutes extraites par pdfplumber.

        Returns:
            Tuple (liste de MatiereExtraction, dict footer avec
            absences/retards/appreciation_globale).
        """
        if not tables:
            return [], {}

        min_rows = self._tables.get("min_rows", 2)
        footer_marker = self._tables.get("footer_marker", "Absences")
        col_cfg = self._tables.get("columns", {})
        col_matiere = col_cfg.get("matiere_and_prof", col_cfg.get("matiere_nom", 0))
        col_notes = col_cfg.get("notes", 1)
        col_appreciation = col_cfg.get("appreciation", 3)
        prof_in_col = self._tables.get("prof_in_matiere_col", False)
        min_appr_len = self._tables.get("min_appreciation_length", 5)

        matieres: list[MatiereExtraction] = []
        footer_data: dict = {}

        for table in tables:
            if len(table) < min_rows:
                continue

            for row in table:
                if not row or len(row) < 2:
                    continue

                cell0 = row[col_matiere] or ""

                # Detecter le footer
                if re.search(footer_marker, cell0, re.IGNORECASE):
                    footer_data = self._parse_footer_row(row)
                    continue

                # Splitter col 0 par \n
                lines = [ln.strip() for ln in cell0.split("\n") if ln.strip()]
                if not lines:
                    continue

                # Ligne 1 = nom matiere (nettoyer prof + Ecrit/Oral inline)
                nom_matiere = lines[0]
                # Retirer prof inline : "ANGLAIS LV1 Mme AJENJO ..." → "ANGLAIS LV1"
                nom_matiere = re.sub(
                    r"\s+(?:Mme?\.?|M\.?)\s+\S+.*$", "", nom_matiere
                ).strip()
                # Retirer labels Ecrit/Oral residuels
                nom_matiere = re.sub(
                    r"\s+(?:[EÉ]crit|[Oo]ral)(?:\s+(?:[EÉ]crit|[Oo]ral))*\s*$",
                    "",
                    nom_matiere,
                ).strip()

                # Extraire prof(s) depuis col 0 (lignes separees OU inline)
                profs = []
                if prof_in_col:
                    # Prof inline dans lines[0]
                    prof_inline = re.search(r"((?:Mme?\.?|M\.?)\s+\S+)", lines[0])
                    if prof_inline:
                        profs.append(prof_inline.group(1).strip())
                    # Profs sur lignes separees
                    for ln in lines[1:]:
                        if re.match(r"^(?:Mme?\.?|M\.?)\s", ln):
                            profs.append(ln.strip())
                # Nettoyer Ecrit/Oral des noms de profs
                profs = [
                    re.sub(
                        r"\s+(?:[EÉ]crit|[Oo]ral)(?:\s+(?:[EÉ]crit|[Oo]ral))*\s*$",
                        "",
                        p,
                    ).strip()
                    for p in profs
                ]
                professeur = ", ".join(profs) if profs else None

                # Parser col notes — premiere valeur = moyenne eleve
                cell_notes = row[col_notes] if len(row) > col_notes else ""
                moyenne_eleve = extract_number(cell_notes)

                # Ignorer les lignes sans notes (headers, titres)
                if moyenne_eleve is None:
                    continue

                # Appreciation (col 3 ou derniere colonne non vide)
                appreciation = ""
                if len(row) > col_appreciation:
                    appr_text = " ".join((row[col_appreciation] or "").split()).strip()
                    if appr_text and len(appr_text) >= min_appr_len:
                        appreciation = appr_text

                if not appreciation:
                    # Fallback: derniere colonne non vide
                    for cell in reversed(row[2:]):
                        text = " ".join((cell or "").split()).strip()
                        if text and len(text) >= min_appr_len:
                            appreciation = text
                            break

                matieres.append(
                    MatiereExtraction(
                        nom=nom_matiere,
                        professeur=professeur,
                        moyenne_eleve=moyenne_eleve,
                        appreciation=appreciation,
                    )
                )

        return matieres, footer_data

    def _parse_footer_row(self, row: list) -> dict:
        """Extrait absences, retards et appreciation globale depuis la ligne footer.

        Le footer PRONOTE contient typiquement :
        "Absences : 5 demi-journees justifiees - Aucun retard
         Appreciation globale : Bilan positif..."

        Args:
            row: Ligne de table contenant le footer.

        Returns:
            Dict avec absences, retards, absences_justifiees, appreciation_globale.
        """
        # Concatener toutes les cellules non vides pour couvrir les deux formats
        text = "\n".join((cell or "") for cell in row)

        result: dict = {}

        # Absences
        absences_str = extract_key_value(text, r"Absences?")
        if absences_str:
            absences_num = extract_number(absences_str)
            if absences_num is not None:
                result["absences"] = int(absences_num)
            if "justifi" in absences_str.lower():
                result["absences_justifiees"] = True

        # Retards
        retards_str = extract_key_value(text, r"Retards?")
        if retards_str:
            retards_num = extract_number(retards_str)
            if retards_num is not None:
                result["retards"] = int(retards_num)

        # "Aucun retard" dans le texte libre (pas en key_value)
        if "retards" not in result and re.search(r"[Aa]ucun\s+retard", text):
            result["retards"] = 0

        # Aussi chercher retards sur la meme ligne que absences
        # ex: "5 demi-journees justifiees - 2 retards"
        if "retards" not in result and absences_str:
            retard_match = re.search(r"(\d+)\s+retards?", absences_str, re.IGNORECASE)
            if retard_match:
                result["retards"] = int(retard_match.group(1))

        return result
