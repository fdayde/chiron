"""Centralized regex patterns for bulletin parsing.

All patterns are compiled for performance and centralized here
to avoid duplication and make maintenance easier.
"""

import re

# =============================================================================
# Compiled regex patterns
# =============================================================================

PATTERNS: dict[str, re.Pattern[str]] = {
    # Student name - matches "Élève : NOM Prénom" or "Nom : NOM Prénom"
    # Captures: group(1) = NOM (uppercase), group(2) = Prénom
    "nom_prenom": re.compile(
        r"(?:Élève|Elève|Nom)\s*:\s*"
        r"([A-ZÉÈÊËÀÂÄÙÛÜÔÖÎÏÇ][A-ZÉÈÊËÀÂÄÙÛÜÔÖÎÏÇ\s-]*?)\s+"
        r"([A-ZÉÈÊËÀÂÄÙÛÜÔÖÎÏÇ][a-zéèêëàâäùûüôöîïç]+(?:\s*-\s*[A-Za-zéèêëàâäùûüôöîïç]+)?)",
        re.IGNORECASE,
    ),
    # Alternative: Prénom NOM format
    "prenom_nom": re.compile(
        r"(?:Élève|Elève|Nom)\s*:\s*"
        r"([A-ZÉÈÊËÀÂÄÙÛÜÔÖÎÏÇ][a-zéèêëàâäùûüôöîïç]+(?:\s*-\s*[A-Za-zéèêëàâäùûüôöîïç]+)?)\s+"
        r"([A-ZÉÈÊËÀÂÄÙÛÜÔÖÎÏÇ][A-ZÉÈÊËÀÂÄÙÛÜÔÖÎÏÇ\s-]+)",
        re.IGNORECASE,
    ),
    # Classe - matches "Classe : 5ème A" or "Classe : 5A" or "Classe : 5EME A"
    "classe": re.compile(
        r"(?:Classe|Niveau)\s*:\s*(\d+[èeÈE]?[mM]?[eE]?\s*[A-Za-z]?)",
        re.IGNORECASE,
    ),
    # Trimestre - matches "Trimestre 1", "T1", "1er trimestre", "Trimestre : 2"
    "trimestre": re.compile(
        r"(?:Trimestre\s*:?\s*(\d)|T(\d)|(\d)(?:er|ème|e|eme)?\s*trimestre)",
        re.IGNORECASE,
    ),
    # Absences - matches "Absences : 4 demi-journées" or "4 demi-journées"
    "absences": re.compile(
        r"(?:Absences?\s*:\s*)?(\d+)\s*(?:demi-journées?|1/2\s*j|dj)",
        re.IGNORECASE,
    ),
    # Absences justifiées - matches "(justifiées)" or "(non justifiées)" or "dont X justifiées"
    "absences_justifiees": re.compile(
        r"\(?(non\s+)?justifi[ée]e?s?\)?",
        re.IGNORECASE,
    ),
    # Retards - matches "Retards : 3" or "3 retard(s)"
    "retards": re.compile(
        r"(?:Retards?\s*:\s*)?(\d+)(?:\s*retards?)?",
        re.IGNORECASE,
    ),
    # Note with class average - "12,5 / 14,2" or "12.5 (moy: 15.3)" or "12.5 / 15.3"
    "note_with_moyenne": re.compile(
        r"(\d+[,.]?\d*)\s*[/|]\s*(\d+[,.]?\d*)|"
        r"(\d+[,.]?\d*)\s*\((?:moy|classe|moyenne)\s*:?\s*(\d+[,.]?\d*)\)",
        re.IGNORECASE,
    ),
    # Simple note - "12,5" or "12.5"
    "note_simple": re.compile(
        r"(\d+[,.]?\d*)",
    ),
    # Genre from text markers (feminine forms in French)
    "genre_feminin": re.compile(
        r"\b(?:elle|déléguée|élue|absente|attentive|sérieuse|investie|"
        r"volontaire|impliquée|encourageante|excellente)\b",
        re.IGNORECASE,
    ),
    # Genre from text markers (masculine forms in French)
    "genre_masculin": re.compile(
        r"\b(?:il|délégué|élu|absent|attentif|sérieux|investi|"
        r"volontaire|impliqué|encourageant|excellent)\b",
        re.IGNORECASE,
    ),
    # Engagements - matches "Délégué(e) titulaire", "Éco-délégué", etc.
    "engagement": re.compile(
        r"((?:Délégué|Déléguée|Éco-délégué|Éco-déléguée|Représentant|Représentante)"
        r"(?:\s+(?:titulaire|suppléant|suppléante|de classe|élève))?)",
        re.IGNORECASE,
    ),
}


# =============================================================================
# Extraction helper functions
# =============================================================================


def extract_field(pattern_name: str, text: str) -> str | None:
    """Extract first match for a named pattern.

    Args:
        pattern_name: Name of pattern in PATTERNS dict.
        text: Text to search in.

    Returns:
        First captured group or None if no match.

    Example:
        >>> extract_field("trimestre", "Trimestre 2")
        "2"
    """
    pattern = PATTERNS.get(pattern_name)
    if not pattern:
        return None

    match = pattern.search(text)
    if not match:
        return None

    # Return first non-None group
    for group in match.groups():
        if group is not None:
            return group.strip()

    return None


def extract_all_groups(pattern_name: str, text: str) -> tuple[str, ...] | None:
    """Extract all captured groups for a named pattern.

    Args:
        pattern_name: Name of pattern in PATTERNS dict.
        text: Text to search in.

    Returns:
        Tuple of all captured groups, or None if no match.

    Example:
        >>> extract_all_groups("nom_prenom", "Élève : DUPONT Marie")
        ("DUPONT", "Marie")
    """
    pattern = PATTERNS.get(pattern_name)
    if not pattern:
        return None

    match = pattern.search(text)
    if not match:
        return None

    # Filter out None groups
    groups = tuple(g.strip() for g in match.groups() if g is not None)
    return groups if groups else None


def extract_all_matches(pattern_name: str, text: str) -> list[str]:
    """Extract all matches for a named pattern.

    Args:
        pattern_name: Name of pattern in PATTERNS dict.
        text: Text to search in.

    Returns:
        List of all matches (first captured group from each).

    Example:
        >>> extract_all_matches("engagement", "Délégué titulaire, Éco-délégué")
        ["Délégué titulaire", "Éco-délégué"]
    """
    pattern = PATTERNS.get(pattern_name)
    if not pattern:
        return []

    results = []
    for match in pattern.finditer(text):
        for group in match.groups():
            if group is not None:
                results.append(group.strip())
                break  # Only first non-None group per match

    return results


def detect_genre(text: str) -> str | None:
    """Detect genre from grammatical markers in French text.

    Analyzes text for feminine/masculine word forms to infer gender.

    Args:
        text: Text to analyze (typically teacher appreciations).

    Returns:
        "F" for feminine, "M" for masculine, None if undetermined.

    Example:
        >>> detect_genre("Elle est très sérieuse et investie.")
        "F"
    """
    fem_matches = len(PATTERNS["genre_feminin"].findall(text))
    masc_matches = len(PATTERNS["genre_masculin"].findall(text))

    if fem_matches > masc_matches:
        return "F"
    elif masc_matches > fem_matches:
        return "M"

    return None


def extract_nom_prenom(text: str) -> tuple[str | None, str | None]:
    """Extract nom and prénom from text.

    Tries multiple patterns to handle different formats.

    Args:
        text: Text containing student name.

    Returns:
        Tuple of (nom, prenom), with None for missing values.
    """
    # Try NOM Prénom format first
    groups = extract_all_groups("nom_prenom", text)
    if groups and len(groups) >= 2:
        return groups[0], groups[1]

    # Try Prénom NOM format
    groups = extract_all_groups("prenom_nom", text)
    if groups and len(groups) >= 2:
        return groups[1], groups[0]  # Swap order

    return None, None


def extract_notes(text: str) -> tuple[float | None, float | None]:
    """Extract student note and class average from text.

    Args:
        text: Cell content with note(s).

    Returns:
        Tuple of (moyenne_eleve, moyenne_classe), with None for missing.

    Example:
        >>> extract_notes("12,5 / 14,2")
        (12.5, 14.2)
    """
    # Try note with moyenne pattern first
    groups = extract_all_groups("note_with_moyenne", text)
    if groups:
        # Find the two numeric values
        nums = [_parse_float(g) for g in groups if g]
        nums = [n for n in nums if n is not None]
        if len(nums) >= 2:
            return nums[0], nums[1]
        elif len(nums) == 1:
            return nums[0], None

    # Try simple note
    simple = extract_field("note_simple", text)
    if simple:
        return _parse_float(simple), None

    return None, None


def _parse_float(value: str | None) -> float | None:
    """Parse float from string, handling French comma format.

    Args:
        value: String to parse.

    Returns:
        Float value or None if parsing fails.
    """
    if not value:
        return None

    try:
        # Replace French comma with dot
        cleaned = value.replace(",", ".").strip()
        return float(cleaned)
    except (ValueError, AttributeError):
        return None
