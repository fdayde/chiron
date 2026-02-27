"""Pipeline de pseudonymisation 3 passes.

Pass 1 — Regex accent-insensitive (+ variantes tiret→espace)
Pass 2 — Flair NER + fuzzy matching (seuil adaptatif)
Pass 3 — Fuzzy direct mot-par-mot (filtre majuscule + seuil adaptatif)
"""

import logging
import re
import threading
import unicodedata

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Accent-insensitive regex helpers (moved from exports.py)
# ---------------------------------------------------------------------------

_ACCENT_MAP: dict[str, str] = {
    "a": "[aàáâãäå]",
    "c": "[cç]",
    "e": "[eèéêë]",
    "i": "[iìíîï]",
    "n": "[nñ]",
    "o": "[oòóôõö]",
    "u": "[uùúûü]",
    "y": "[yýÿ]",
}


def _make_accent_insensitive_pattern(s: str) -> str:
    """Convert a string into an accent-insensitive regex pattern.

    Each character (accented or not) is replaced by a character class
    containing all its accent variants.

    Example: 'Grégorio' → 'Gr[eèéêë]gorio'
    """
    result: list[str] = []
    for char in s:
        # NFD décompose un caractère accentué en lettre base + diacritique.
        # Ex: "é" → "e" + "\u0301".  [0] extrait la lettre base "e".
        base_char = unicodedata.normalize("NFD", char)[0].lower()
        if base_char in _ACCENT_MAP:
            result.append(_ACCENT_MAP[base_char])
        else:
            result.append(re.escape(char))
    return "".join(result)


# ---------------------------------------------------------------------------
# Fuzzy helpers
# ---------------------------------------------------------------------------


def normalize_for_fuzzy(s: str) -> str:
    """Lowercase + strip accents for fuzzy comparison.

    Different from ``normalize_name`` in utils.py which preserves accents.
    """
    s = s.lower()
    # NFD décompose chaque caractère accentué en lettre base + diacritique(s).
    # Ex: "héloïse" → "h" "e" "\u0301" "l" "o" "i" "\u0308" "s" "e"
    # On filtre les diacritiques (catégorie Unicode "Mn" = Mark, nonspacing)
    # pour ne garder que les lettres base → "heloise".
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def get_fuzzy_threshold(word: str) -> float | None:
    """Return the fuzzy threshold adapted to the word length.

    ≤ 3 chars → None (exact only, no fuzzy)
    4-5 chars → 92  (very strict, avoids noté~Noé)
    6+ chars  → 83  (permissive, catches typos without Manque~Manuel collisions)
    """
    n = len(word)
    if n <= 3:
        return None
    elif n <= 5:
        return 92
    else:
        return 83


# ---------------------------------------------------------------------------
# Flair NER (lazy + thread-safe)
# ---------------------------------------------------------------------------

_flair_tagger = None
_flair_lock = threading.Lock()


def _get_flair_tagger():
    """Load the Flair NER tagger (lazy, thread-safe double-check locking)."""
    global _flair_tagger
    if _flair_tagger is None:
        with _flair_lock:
            if _flair_tagger is None:
                # Pre-import transformers submodules that flair needs but that
                # transformers' lazy loader fails to resolve in PyInstaller bundles.
                import transformers.models.auto.feature_extraction_auto  # noqa: F401
                import transformers.models.auto.tokenization_auto  # noqa: F401
                from flair.models import SequenceTagger

                logger.info("Chargement du modèle Flair NER: flair/ner-french")
                _flair_tagger = SequenceTagger.load("flair/ner-french")
    return _flair_tagger


def flair_ner_persons(text: str) -> list[dict]:
    """Extract PER entities from *text* using Flair NER."""
    from flair.data import Sentence

    tagger = _get_flair_tagger()
    sentence = Sentence(text)
    tagger.predict(sentence)
    return [
        {"word": e.text, "score": e.get_label("ner").score}
        for e in sentence.get_spans("ner")
        if e.get_label("ner").value == "PER"
    ]


# ---------------------------------------------------------------------------
# has_fuzzy_match
# ---------------------------------------------------------------------------


def has_fuzzy_match(word_parts: set[str], nom_parts: set[str]) -> tuple[bool, str]:
    """Check whether at least one *word_part* matches a *nom_part*.

    Uses adaptive thresholds based on word length.
    """
    for wp in word_parts:
        threshold = get_fuzzy_threshold(wp)
        for np in nom_parts:
            if threshold is None:
                if wp == np:
                    return True, f"{wp}=={np} (exact, ≤3)"
            else:
                ratio = fuzz.ratio(wp, np)
                if ratio >= threshold:
                    return True, f"{wp}~{np} (ratio={ratio:.0f}, seuil={threshold})"
    return False, ""


# ---------------------------------------------------------------------------
# Pass 1 — Regex accent-insensitive
# ---------------------------------------------------------------------------


def regex_pass(text: str, nom: str, prenom: str, eleve_id: str) -> tuple[str, bool]:
    """Replace exact (accent/case insensitive) occurrences of nom/prenom.

    For hyphenated names, also generates the space variant.
    """
    original = text
    variants: list[str] = []
    if prenom and nom:
        variants.append(f"{prenom} {nom}")
        variants.append(f"{nom} {prenom}")
    if nom:
        variants.append(nom)
    if prenom:
        variants.append(prenom)

    # Generate hyphen→space variants
    extra = [v.replace("-", " ") for v in variants if "-" in v]
    variants.extend(extra)

    # Deduplicate preserving order (longest first)
    seen: set[str] = set()
    unique: list[str] = []
    for v in variants:
        key = v.lower()
        if key not in seen:
            seen.add(key)
            unique.append(v)

    for variant in unique:
        pattern_str = _make_accent_insensitive_pattern(variant)
        pattern = re.compile(rf"\b{pattern_str}\b", re.IGNORECASE)
        text = pattern.sub(eleve_id, text)

    return text, text != original


# ---------------------------------------------------------------------------
# Pass 2 — Flair NER + fuzzy
# ---------------------------------------------------------------------------


def ner_fuzzy_pass(
    text: str, nom_parts: set[str], eleve_id: str
) -> tuple[str, list[str]]:
    """Detect PER entities close to the known name via Flair NER + fuzzy."""
    steps: list[str] = []
    entities = flair_ner_persons(text)
    for e in entities:
        word = e["word"].strip()
        word_parts = {p.lower() for p in word.split() if len(p) > 1}
        matched, detail = has_fuzzy_match(word_parts, nom_parts)
        if matched:
            pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
            text = pattern.sub(eleve_id, text)
            steps.append(f"ner_fuzzy({detail})")
    return text, steps


# ---------------------------------------------------------------------------
# Pass 3 — Fuzzy direct word-by-word
# ---------------------------------------------------------------------------


def fuzzy_word_scan(
    text: str, nom_parts: set[str], eleve_id: str
) -> tuple[str, list[str]]:
    """Word-by-word scan with fuzzy Levenshtein and adaptive threshold.

    Only words starting with an uppercase letter are candidates: a common
    lowercase word ("français") must not match a proper name ("Francois").
    """
    details: list[str] = []
    words = re.findall(r"\b[\w'-]+\b", text)
    for word in words:
        if not word[0].isupper():
            continue

        threshold = get_fuzzy_threshold(word)
        if threshold is None:
            continue  # ≤3 chars: no fuzzy direct (regex is enough)

        word_norm = normalize_for_fuzzy(word)
        for np in nom_parts:
            np_norm = normalize_for_fuzzy(np)
            ratio = fuzz.ratio(word_norm, np_norm)
            if ratio >= threshold and word.lower() != np.lower():
                pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
                text = pattern.sub(eleve_id, text)
                details.append(
                    f"'{word}'~'{np}' (ratio={ratio:.0f}, seuil={threshold})"
                )
                break
    return text, details


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def pseudonymize(text: str, nom: str, prenom: str, eleve_id: str) -> str:
    """3-pass pseudonymization pipeline.

    Pass 1 — Regex accent-insensitive (+ hyphen→space variants)
    Pass 2 — Flair NER + fuzzy (adaptive threshold)
    Pass 3 — Fuzzy direct word-by-word (uppercase filter + adaptive threshold)

    Returns the pseudonymized text. Step details are logged at DEBUG level.
    """
    if not text:
        return text

    steps: list[str] = []

    # Pass 1: Regex accent-insensitive
    text, matched = regex_pass(text, nom, prenom, eleve_id)
    if matched:
        steps.append("regex")

    # Pass 2: Flair NER + fuzzy
    nom_parts = {p.lower() for p in [nom, prenom] if p and len(p) > 1}
    text, ner_steps = ner_fuzzy_pass(text, nom_parts, eleve_id)
    steps.extend(ner_steps)

    # Pass 3: Fuzzy direct word-by-word
    text, fuzzy_details = fuzzy_word_scan(text, {nom, prenom}, eleve_id)
    for d in fuzzy_details:
        steps.append(f"fuzzy_direct({d})")

    if steps:
        logger.debug("pseudonymize [%s]: %s", eleve_id, ", ".join(steps))

    return text
