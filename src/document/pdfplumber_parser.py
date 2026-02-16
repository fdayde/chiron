"""Parser PDF utilisant pdfplumber avec extraction de données structurées.

Legacy parser — conservé pour rétrocompatibilité avec PDF_PARSER_TYPE=pdfplumber.
Les utilitaires partagés (extract_key_value, extract_number, etc.) ont été
déplacés vers parser.py. Ce module les réexporte pour ne pas casser les imports.

Extrait les données structurées (notes, appréciations, absences, etc.)
à partir d'un PDF déjà anonymisé.
"""

import logging
from pathlib import Path

from src.core.models import EleveExtraction, MatiereExtraction
from src.document.parser import (
    extract_key_value,
    extract_note_pair,
    extract_number,
    extract_pdf_content,
    parse_engagements,
)

# Réexports pour rétrocompatibilité
__all__ = [
    "extract_key_value",
    "extract_number",
    "extract_note_pair",
    "parse_engagements",
    "parse_raw_tables",
    "PdfplumberParser",
]

logger = logging.getLogger(__name__)


def parse_raw_tables(tables: list) -> list[MatiereExtraction]:
    """Parse les tables brutes en liste de matières.

    Args:
        tables: Liste de tables extraites par pdfplumber.

    Returns:
        Liste de MatiereExtraction.
    """
    if not tables:
        return []

    matieres = []
    for table in tables:
        # Tables à 1 ligne = fragments de métadonnées (ex: nom élève),
        # pas des données de matières
        if len(table) < 2:
            continue

        for row in table:
            if not row or len(row) < 2:
                continue

            # Colonne 0: nom (nettoyer)
            nom = " ".join((row[0] or "").split()).strip()
            if not nom:
                continue

            # Colonne 1: notes
            note_text = " ".join((row[1] or "").split()).strip()
            moy_eleve, moy_classe = extract_note_pair(note_text)

            # Ignorer les lignes sans notes (headers)
            if moy_eleve is None:
                continue

            # Dernière colonne non vide: appréciation
            appreciation = ""
            for cell in reversed(row[2:]):
                text = " ".join((cell or "").split()).strip()
                if text and len(text) > 5:
                    appreciation = text
                    break

            matieres.append(
                MatiereExtraction(
                    nom=nom,
                    moyenne_eleve=moy_eleve,
                    moyenne_classe=moy_classe,
                    appreciation=appreciation,
                )
            )

    return matieres


class PdfplumberParser:
    """Parser PDF utilisant pdfplumber - extraction mécanique avec interprétation.

    Legacy: pour les bulletins de test. Utiliser YamlTemplateParser pour PRONOTE réel.
    """

    def parse(
        self,
        pdf_path: str | Path,
        eleve_id: str,
        genre: str | None = None,
    ) -> EleveExtraction:
        """Parse un PDF anonymisé et extrait les données structurées.

        Args:
            pdf_path: Chemin vers le fichier PDF (anonymisé).
            eleve_id: Identifiant de l'élève (fourni par le flux d'import).
            genre: Genre de l'élève si connu (extrait en amont).

        Returns:
            EleveExtraction avec les données structurées, nom=None.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        logger.info(f"Parsing: {pdf_path.name} (eleve_id={eleve_id})")

        content = extract_pdf_content(pdf_path)

        if not content.tables and not content.text:
            return EleveExtraction(eleve_id=eleve_id, nom=None, prenom=None)

        raw_text = content.text or ""

        # Extraire les champs structurés du texte
        # Note: nom/prenom sont déjà anonymisés, on ne les extrait pas

        # Genre (peut être passé en paramètre ou extrait du texte)
        if not genre:
            genre_str = extract_key_value(raw_text, "Genre")
            if genre_str:
                genre_lower = genre_str.lower()
                if "fille" in genre_lower or "f" == genre_lower:
                    genre = "Fille"
                elif "garçon" in genre_lower or "garcon" in genre_lower:
                    genre = "Garçon"
                elif genre_lower == "m":
                    genre = "Garçon"

        # Absences
        absences_str = extract_key_value(raw_text, r"Absences?")
        absences = int(n) if (n := extract_number(absences_str)) else None
        absences_justifiees = None
        if absences_str and "justifi" in absences_str.lower():
            absences_justifiees = True

        # Engagements
        engagements_str = extract_key_value(raw_text, r"Engagements?")
        engagements = parse_engagements(engagements_str)

        # Moyenne générale
        moyenne_gen_str = extract_key_value(raw_text, r"Moyenne\s+g[ée]n[ée]rale")
        moyenne_generale = extract_number(moyenne_gen_str)

        # Matières (depuis les tables)
        matieres = parse_raw_tables(content.tables)

        return EleveExtraction(
            eleve_id=eleve_id,
            nom=None,  # Anonymisé
            prenom=None,  # Anonymisé
            genre=genre,
            absences_demi_journees=absences,
            absences_justifiees=absences_justifiees,
            engagements=engagements,
            moyenne_generale=moyenne_generale,
            matieres=matieres,
            raw_text=raw_text,
            raw_tables=content.tables,
        )
