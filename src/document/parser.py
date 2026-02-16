"""Utilitaires de base pour le parsing PDF avec pdfplumber."""

import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber


@dataclass
class PDFContent:
    """Contenu extrait d'un PDF."""

    tables: list[list[list[str | None]]] = field(default_factory=list)
    text: str = ""


def extract_pdf_content(pdf_path: str | Path) -> PDFContent:
    """Extrait tableaux et texte d'un PDF en une seule passe.

    Args:
        pdf_path: Chemin vers le fichier PDF.

    Returns:
        PDFContent avec tables et text.
    """
    tables: list[list[list[str | None]]] = []
    text_parts: list[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Tables — snap_x_tolerance fusionne les bordures proches
            # pour éviter les micro-colonnes parasites (ex: bordures Word)
            page_tables = page.extract_tables(table_settings={"snap_x_tolerance": 10})
            if page_tables:
                tables.extend(page_tables)
            # Text
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    return PDFContent(tables=tables, text="\n".join(text_parts))


def clean_text(text: str | None) -> str:
    """Nettoie et normalise un texte extrait.

    Args:
        text: Texte brut à nettoyer.

    Returns:
        Texte nettoyé.
    """
    if not text:
        return ""

    # Normaliser les espaces multiples
    text = re.sub(r"\s+", " ", text)

    # Supprimer espaces en début/fin
    text = text.strip()

    # Normaliser les tirets
    text = re.sub(r"[–—]", "-", text)

    return text


def parse_float(value: str | None) -> float | None:
    """Parse une valeur numérique (note, moyenne).

    Args:
        value: Chaîne représentant un nombre (ex: "12,5" ou "12.5").

    Returns:
        Float ou None si parsing impossible.
    """
    if not value:
        return None

    # Nettoyer
    value = clean_text(value)

    # Remplacer virgule par point
    value = value.replace(",", ".")

    # Supprimer caractères non numériques sauf point
    value = re.sub(r"[^\d.]", "", value)

    try:
        return float(value)
    except ValueError:
        return None


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


def extract_number(text: str | None) -> float | None:
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
