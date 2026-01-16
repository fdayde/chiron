"""Shared validation utilities for Chiron.

Provides reusable validators for common data formats
used throughout the application.
"""

import re
from typing import Literal

# Valid trimestre values
VALID_TRIMESTRES = (1, 2, 3)

# Valid genre values
VALID_GENRES: tuple[Literal["M", "F"], ...] = ("M", "F")

# Valid synthese status values
VALID_STATUSES = ("draft", "generated", "edited", "validated")

# Valid posture values
VALID_POSTURES = ("actif", "passif", "perturbateur", "variable")

# Valid severite values for alerts
VALID_SEVERITES = ("urgent", "attention")

# Regex for classe format (e.g., "5eme A", "3A", "6EME B", "5ème")
CLASSE_PATTERN = re.compile(
    r"^(\d)[èeÈE]?[mM]?[eE]?\s*([A-Za-z])?$",
    re.IGNORECASE,
)


def validate_trimestre(trimestre: int) -> bool:
    """Validate trimestre is 1, 2, or 3.

    Args:
        trimestre: Trimestre number to validate.

    Returns:
        True if valid, False otherwise.

    Examples:
        >>> validate_trimestre(1)
        True
        >>> validate_trimestre(4)
        False
    """
    return trimestre in VALID_TRIMESTRES


def validate_note(note: float) -> bool:
    """Validate note is between 0 and 20.

    Args:
        note: Grade to validate.

    Returns:
        True if valid, False otherwise.

    Examples:
        >>> validate_note(15.5)
        True
        >>> validate_note(-1)
        False
        >>> validate_note(21)
        False
    """
    return 0 <= note <= 20


def validate_classe_format(classe: str) -> bool:
    """Validate classe format.

    Accepts formats like: "5eme A", "3A", "6EME B", "5ème", "4e C"

    Args:
        classe: Classe string to validate.

    Returns:
        True if valid format, False otherwise.

    Examples:
        >>> validate_classe_format("5eme A")
        True
        >>> validate_classe_format("3A")
        True
        >>> validate_classe_format("invalid")
        False
    """
    if not classe:
        return False
    # Normalize common variations
    normalized = classe.strip().replace("ème", "eme").replace("ÈME", "EME")
    return CLASSE_PATTERN.match(normalized) is not None


def validate_genre(genre: str) -> bool:
    """Validate genre is 'M' or 'F'.

    Args:
        genre: Genre to validate.

    Returns:
        True if valid, False otherwise.
    """
    return genre in VALID_GENRES


def validate_status(status: str) -> bool:
    """Validate synthese status.

    Args:
        status: Status to validate.

    Returns:
        True if valid, False otherwise.
    """
    return status in VALID_STATUSES


def validate_posture(posture: str) -> bool:
    """Validate posture generale.

    Args:
        posture: Posture to validate.

    Returns:
        True if valid, False otherwise.
    """
    return posture in VALID_POSTURES


def validate_severite(severite: str) -> bool:
    """Validate alert severite.

    Args:
        severite: Severite to validate.

    Returns:
        True if valid, False otherwise.
    """
    return severite in VALID_SEVERITES


def normalize_classe(classe: str) -> str:
    """Normalize classe format to standard form.

    Converts various formats to "Xeme Y" format (e.g., "5eme A").

    Args:
        classe: Classe string to normalize.

    Returns:
        Normalized classe string.

    Examples:
        >>> normalize_classe("5A")
        "5eme A"
        >>> normalize_classe("3ÈME B")
        "3eme B"
    """
    if not classe:
        return classe

    normalized = classe.strip().upper()
    # Replace various forms of "ème"
    normalized = re.sub(r"[ÈE]ME|ÈME|EME", "eme", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"[ÈE]", "e", normalized, flags=re.IGNORECASE)

    match = CLASSE_PATTERN.match(normalized)
    if match:
        niveau = match.group(1)
        section = match.group(2) or ""
        if section:
            return f"{niveau}eme {section.upper()}"
        return f"{niveau}eme"

    return classe  # Return original if no match


def validate_eleve_id_format(eleve_id: str, prefix: str = "ELEVE_") -> bool:
    """Validate eleve_id follows expected pseudonym format.

    Args:
        eleve_id: ID to validate.
        prefix: Expected prefix (default: "ELEVE_").

    Returns:
        True if valid format, False otherwise.

    Examples:
        >>> validate_eleve_id_format("ELEVE_001")
        True
        >>> validate_eleve_id_format("STUDENT_A", prefix="STUDENT_")
        True
    """
    if not eleve_id:
        return False
    return eleve_id.startswith(prefix) and len(eleve_id) > len(prefix)
