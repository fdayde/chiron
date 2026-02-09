"""Utilitaires partagés."""

import re
import unicodedata


def normalize_name(name: str | None) -> str | None:
    """Normalise un nom pour comparaison anti-doublon.

    Applique : NFC unicode, strip, collapse espaces multiples, lowercase.
    Les accents sont conservés (significatifs en français).

    Args:
        name: Nom à normaliser, ou None.

    Returns:
        Nom normalisé, ou None si l'entrée est None.
    """
    if name is None:
        return None
    name = unicodedata.normalize("NFC", name)
    name = name.strip()
    name = re.sub(r"\s+", " ", name)
    name = name.lower()
    return name
