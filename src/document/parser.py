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
