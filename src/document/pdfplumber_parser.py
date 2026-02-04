"""Parser PDF utilisant pdfplumber avec extraction de données structurées.

Extrait les données brutes ET les champs structurés (nom, genre, notes, etc.)
à partir du texte et des tableaux.
"""

import logging
import re
from pathlib import Path

from src.core.models import EleveExtraction, MatiereExtraction
from src.document.parser import extract_pdf_content

logger = logging.getLogger(__name__)


def extract_key_value(text: str, key: str) -> str | None:
    """Extrait une valeur pour une clé donnée.

    Gère deux formats :
    - 'Key : Value' (même ligne)
    - 'Key\\n: Value' (ligne séparée, format Docling)

    Args:
        text: Texte source.
        key: Clé à rechercher (peut être une regex).

    Returns:
        Valeur extraite ou None.
    """
    if not text:
        return None
    # Format standard: Key : Value
    pattern = rf"{key}\s*:\s*([^\n]+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Format Docling: Key\n: Value
    pattern_docling = rf"{key}\s*\n\s*:\s*([^\n]+)"
    match = re.search(pattern_docling, text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def extract_number(text: str) -> float | None:
    """Extrait le premier nombre d'un texte.

    Args:
        text: Texte contenant potentiellement un nombre.

    Returns:
        Nombre extrait ou None.
    """
    if not text:
        return None
    match = re.search(r"(\d+[,.]?\d*)", text)
    if match:
        return float(match.group(1).replace(",", "."))
    return None


def extract_note_pair(text: str) -> tuple[float | None, float | None]:
    """Extrait une paire de notes (élève / classe).

    Args:
        text: Texte contenant les notes (ex: "15.21 / 10.83").

    Returns:
        Tuple (note_eleve, note_classe).
    """
    if not text:
        return None, None
    match = re.search(r"(\d+[,.]?\d*)\s*[/|]\s*(\d+[,.]?\d*)", text)
    if match:
        return (
            float(match.group(1).replace(",", ".")),
            float(match.group(2).replace(",", ".")),
        )
    # Fallback: juste un nombre
    num = extract_number(text)
    return num, None


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


def parse_engagements(text: str | None) -> list[str]:
    """Parse les engagements depuis le texte.

    Args:
        text: Valeur du champ Engagements.

    Returns:
        Liste d'engagements.
    """
    if not text:
        return []
    # Séparer par virgule ou point-virgule
    return [e.strip() for e in re.split(r"[,;]", text) if e.strip()]


class PdfplumberParser:
    """Parser PDF utilisant pdfplumber - extraction mécanique avec interprétation."""

    def parse(self, pdf_path: str | Path) -> list[EleveExtraction]:
        """Parse PDF et extrait les données structurées.

        Args:
            pdf_path: Path to PDF file.

        Returns:
            List with one EleveExtraction containing structured data.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        logger.info(f"Parsing: {pdf_path.name}")

        content = extract_pdf_content(pdf_path)

        if not content.tables and not content.text:
            return []

        raw_text = content.text or ""

        logger.info(f"Raw text (first 500 chars): {raw_text[:500]}")

        # Extraire les champs structurés du texte
        eleve_str = extract_key_value(raw_text, r"[ÉE]l[èe]ve")
        logger.info(f"Extracted eleve_str: {eleve_str}")
        nom = None
        prenom = None
        if eleve_str:
            # Format attendu: "Prénom Nom" ou "Nom"
            parts = eleve_str.split()
            if len(parts) >= 2:
                prenom = parts[0]
                nom = " ".join(parts[1:])
            else:
                nom = eleve_str

        genre_str = extract_key_value(raw_text, "Genre")
        genre = None
        if genre_str:
            genre_lower = genre_str.lower()
            if "fille" in genre_lower or "f" == genre_lower:
                genre = "Fille"
            elif (
                "garçon" in genre_lower or "garcon" in genre_lower or "m" == genre_lower
            ):
                genre = "Garçon"

        absences_str = extract_key_value(raw_text, r"Absences?")
        absences = int(n) if (n := extract_number(absences_str)) else None
        absences_justifiees = None
        if absences_str and "justifi" in absences_str.lower():
            absences_justifiees = True

        engagements_str = extract_key_value(raw_text, r"Engagements?")
        engagements = parse_engagements(engagements_str)

        moyenne_gen_str = extract_key_value(raw_text, r"Moyenne\s+g[ée]n[ée]rale")
        moyenne_generale = extract_number(moyenne_gen_str)

        # Extraire les matières des tables
        matieres = parse_raw_tables(content.tables)

        return [
            EleveExtraction(
                nom=nom,
                prenom=prenom,
                genre=genre,
                absences_demi_journees=absences,
                absences_justifiees=absences_justifiees,
                engagements=engagements,
                moyenne_generale=moyenne_generale,
                matieres=matieres,
                raw_text=raw_text,
                raw_tables=content.tables,
            )
        ]
