"""Tests for the 3-pass pseudonymization pipeline (pseudonymization.py)."""

from __future__ import annotations

from src.document.pseudonymization import (
    fuzzy_word_scan,
    get_fuzzy_threshold,
    has_fuzzy_match,
    normalize_for_fuzzy,
    pseudonymize,
    regex_pass,
)

ELEVE = "ELEVE_001"


# =============================================================================
# normalize_for_fuzzy
# =============================================================================


class TestNormalizeForFuzzy:
    def test_strip_accents(self):
        assert normalize_for_fuzzy("Grégorio") == "gregorio"

    def test_lowercase(self):
        assert normalize_for_fuzzy("DUPONT") == "dupont"

    def test_cedilla(self):
        assert normalize_for_fuzzy("François") == "francois"

    def test_diaeresis(self):
        assert normalize_for_fuzzy("Héloïse") == "heloise"

    def test_plain(self):
        assert normalize_for_fuzzy("Martin") == "martin"


# =============================================================================
# get_fuzzy_threshold
# =============================================================================


class TestGetFuzzyThreshold:
    def test_short_3(self):
        """≤3 chars → None (exact only)."""
        assert get_fuzzy_threshold("Ali") is None
        assert get_fuzzy_threshold("Noé") is None
        assert get_fuzzy_threshold("Léa") is None

    def test_medium_4_5(self):
        """4-5 chars → 92."""
        assert get_fuzzy_threshold("Yann") == 92
        assert get_fuzzy_threshold("Petit") == 92

    def test_long_6_plus(self):
        """6+ chars → 83."""
        assert get_fuzzy_threshold("Martin") == 83
        assert get_fuzzy_threshold("Dupont") == 83
        assert get_fuzzy_threshold("Grégorio") == 83


# =============================================================================
# regex_pass
# =============================================================================


class TestRegexPass:
    def test_exact_match(self):
        text, changed = regex_pass("Dupont est sérieux.", "Dupont", "Marie", ELEVE)
        assert "Dupont" not in text
        assert ELEVE in text
        assert changed

    def test_accent_insensitive(self):
        text, changed = regex_pass("Gregorio participe.", "Dupont", "Grégorio", ELEVE)
        assert "Gregorio" not in text
        assert changed

    def test_case_insensitive(self):
        text, changed = regex_pass(
            "DUPONT MARIE est absente.", "Dupont", "Marie", ELEVE
        )
        assert "DUPONT" not in text
        assert "MARIE" not in text
        assert changed

    def test_hyphen_to_space_variant(self):
        text, changed = regex_pass(
            "Jean Pierre est appliqué.", "Martin", "Jean-Pierre", ELEVE
        )
        assert "Jean Pierre" not in text
        assert changed

    def test_hyphen_original(self):
        text, changed = regex_pass(
            "Jean-Pierre est appliqué.", "Martin", "Jean-Pierre", ELEVE
        )
        assert "Jean-Pierre" not in text
        assert changed

    def test_word_boundary(self):
        text, _ = regex_pass("Mariette travaille bien.", "Dupont", "Marie", ELEVE)
        assert "Mariette" in text

    def test_no_change_returns_false(self):
        text, changed = regex_pass("Bon travail.", "Dupont", "Marie", ELEVE)
        assert not changed
        assert text == "Bon travail."


# =============================================================================
# fuzzy_word_scan
# =============================================================================


class TestFuzzyWordScan:
    def test_uppercase_filter_skips_lowercase(self):
        """Lowercase 'français' must NOT match 'Francois'."""
        text, details = fuzzy_word_scan(
            "Le cours de français est bien.", {"Francois"}, ELEVE
        )
        assert details == []
        assert "français" in text

    def test_uppercase_typo_matches(self):
        """Uppercase 'Françoi' (typo) should match 'Francois'."""
        text, details = fuzzy_word_scan("Françoi participe.", {"Francois"}, ELEVE)
        assert len(details) == 1
        assert ELEVE in text

    def test_short_word_skipped(self):
        """≤3 chars words are not fuzzy-scanned."""
        text, details = fuzzy_word_scan("Ali est bon.", {"Ali"}, ELEVE)
        assert details == []

    def test_exact_match_skipped(self):
        """Exact lowercase match (already handled by regex) is skipped."""
        text, details = fuzzy_word_scan("Dupont progresse.", {"Dupont"}, ELEVE)
        assert details == []


# =============================================================================
# has_fuzzy_match
# =============================================================================


class TestHasFuzzyMatch:
    def test_exact_short(self):
        matched, _ = has_fuzzy_match({"ali"}, {"ali"})
        assert matched

    def test_no_match_short_different(self):
        matched, _ = has_fuzzy_match({"ami"}, {"ali"})
        assert not matched

    def test_fuzzy_long(self):
        matched, _ = has_fuzzy_match({"grégorrio"}, {"grégorio"})
        assert matched

    def test_no_fuzzy_too_different(self):
        matched, _ = has_fuzzy_match({"xyz"}, {"abc"})
        assert not matched


# =============================================================================
# pseudonymize (integrated pipeline, NER mocked in conftest)
# =============================================================================


class TestPseudonymize:
    def test_exact_name(self):
        result = pseudonymize("Dupont est sérieux.", "Dupont", "Marie", ELEVE)
        assert "Dupont" not in result
        assert ELEVE in result

    def test_full_name(self):
        result = pseudonymize("Marie Dupont travaille bien.", "Dupont", "Marie", ELEVE)
        assert "Marie" not in result
        assert "Dupont" not in result

    def test_no_name_unchanged(self):
        original = "Bon travail ce trimestre."
        assert pseudonymize(original, "Dupont", "Marie", ELEVE) == original

    def test_empty_text(self):
        assert pseudonymize("", "Dupont", "Marie", ELEVE) == ""

    def test_accented_name(self):
        result = pseudonymize(
            "Héloïse Béranger participe.", "Béranger", "Héloïse", ELEVE
        )
        assert "Héloïse" not in result
        assert "Béranger" not in result

    def test_accented_stripped(self):
        result = pseudonymize("Heloise progresse.", "Béranger", "Héloïse", ELEVE)
        assert "Heloise" not in result

    def test_hyphenated_prenom(self):
        result = pseudonymize(
            "Jean-Pierre est appliqué.", "Martin", "Jean-Pierre", ELEVE
        )
        assert "Jean-Pierre" not in result

    def test_hyphen_as_space(self):
        result = pseudonymize(
            "Jean Pierre a progressé.", "Martin", "Jean-Pierre", ELEVE
        )
        assert "Jean Pierre" not in result

    def test_multiple_occurrences(self):
        result = pseudonymize(
            "Marie travaille. Marie doit lire.", "Dupont", "Marie", ELEVE
        )
        assert result.count(ELEVE) == 2
        assert "Marie" not in result

    def test_word_boundary_mariette(self):
        result = pseudonymize("Mariette travaille.", "Dupont", "Marie", ELEVE)
        assert "Mariette" in result

    def test_note_not_noe(self):
        """'noté' must NOT match 'Noé' (lowercase + different word)."""
        result = pseudonymize("Il a noté ses devoirs.", "Petit", "Noé", ELEVE)
        assert "noté" in result
