"""Tests de _pseudonymize_extraction — regex de remplacement des noms."""

from __future__ import annotations

from src.api.routers.exports import _pseudonymize_extraction
from src.core.models import EleveExtraction, MatiereExtraction


def _make_eleve(appreciation: str, raw_text: str = "") -> EleveExtraction:
    """Helper pour créer un élève avec une seule matière."""
    return EleveExtraction(
        eleve_id="ELEVE_001",
        classe="5A",
        trimestre=1,
        matieres=[MatiereExtraction(nom="Maths", appreciation=appreciation)],
        raw_text=raw_text or None,
    )


def _identity(nom: str, prenom: str) -> dict:
    return {"nom": nom, "prenom": prenom, "nom_complet": f"{nom} {prenom}"}


# =============================================================================
# Remplacement basique
# =============================================================================


class TestBasicReplacement:
    def test_full_name(self):
        eleve = _make_eleve("Dupont Marie travaille bien.")
        _pseudonymize_extraction(eleve, _identity("Dupont", "Marie"), "ELEVE_001")
        assert "Dupont" not in eleve.matieres[0].appreciation
        assert "Marie" not in eleve.matieres[0].appreciation
        assert "ELEVE_001" in eleve.matieres[0].appreciation

    def test_prenom_only(self):
        eleve = _make_eleve("Marie est sérieuse en classe.")
        _pseudonymize_extraction(eleve, _identity("Dupont", "Marie"), "ELEVE_001")
        assert "Marie" not in eleve.matieres[0].appreciation
        assert "ELEVE_001" in eleve.matieres[0].appreciation

    def test_nom_only(self):
        eleve = _make_eleve("Dupont progresse régulièrement.")
        _pseudonymize_extraction(eleve, _identity("Dupont", "Marie"), "ELEVE_001")
        assert "Dupont" not in eleve.matieres[0].appreciation

    def test_reversed_order(self):
        eleve = _make_eleve("Marie Dupont a de bons résultats.")
        _pseudonymize_extraction(eleve, _identity("Dupont", "Marie"), "ELEVE_001")
        assert "Marie" not in eleve.matieres[0].appreciation
        assert "Dupont" not in eleve.matieres[0].appreciation


# =============================================================================
# Casse et variantes
# =============================================================================


class TestCaseVariants:
    def test_uppercase(self):
        eleve = _make_eleve("DUPONT MARIE est absente.")
        _pseudonymize_extraction(eleve, _identity("Dupont", "Marie"), "ELEVE_001")
        assert "DUPONT" not in eleve.matieres[0].appreciation
        assert "MARIE" not in eleve.matieres[0].appreciation

    def test_lowercase(self):
        eleve = _make_eleve("dupont marie participe peu.")
        _pseudonymize_extraction(eleve, _identity("Dupont", "Marie"), "ELEVE_001")
        assert "dupont" not in eleve.matieres[0].appreciation
        assert "marie" not in eleve.matieres[0].appreciation

    def test_mixed_case(self):
        eleve = _make_eleve("DUPONT marie doit progresser.")
        _pseudonymize_extraction(eleve, _identity("Dupont", "Marie"), "ELEVE_001")
        assert "DUPONT" not in eleve.matieres[0].appreciation
        assert "marie" not in eleve.matieres[0].appreciation


# =============================================================================
# Noms composés et accents
# =============================================================================


class TestComposedAndAccented:
    def test_hyphenated_prenom(self):
        eleve = _make_eleve("Jean-Pierre est un élève sérieux.")
        _pseudonymize_extraction(eleve, _identity("Duval", "Jean-Pierre"), "ELEVE_001")
        assert "Jean-Pierre" not in eleve.matieres[0].appreciation

    def test_accented_name(self):
        eleve = _make_eleve("Héloïse Béziat participe activement.")
        _pseudonymize_extraction(eleve, _identity("Béziat", "Héloïse"), "ELEVE_001")
        assert "Héloïse" not in eleve.matieres[0].appreciation
        assert "Béziat" not in eleve.matieres[0].appreciation

    def test_multi_word_nom(self):
        """Nom composé avec particule (De La Fontaine)."""
        eleve = _make_eleve("De La Fontaine Jean montre de l'intérêt.")
        _pseudonymize_extraction(
            eleve,
            {
                "nom": "De La Fontaine",
                "prenom": "Jean",
                "nom_complet": "De La Fontaine Jean",
            },
            "ELEVE_001",
        )
        assert "De La Fontaine" not in eleve.matieres[0].appreciation


# =============================================================================
# Champs pseudonymisés
# =============================================================================


class TestAllFieldsPseudonymized:
    def test_appreciation_generale_pseudonymized(self):
        eleve = _make_eleve("Marie participe.")
        eleve.appreciation_generale = "Marie Dupont est une élève sérieuse."
        _pseudonymize_extraction(eleve, _identity("Dupont", "Marie"), "ELEVE_001")
        assert "Marie" not in eleve.appreciation_generale
        assert "Dupont" not in eleve.appreciation_generale

    def test_multiple_matieres(self):
        eleve = EleveExtraction(
            eleve_id="ELEVE_001",
            classe="5A",
            trimestre=1,
            matieres=[
                MatiereExtraction(nom="Maths", appreciation="Marie travaille bien."),
                MatiereExtraction(
                    nom="Français", appreciation="Dupont Marie est sérieuse."
                ),
                MatiereExtraction(nom="SVT", appreciation="Bon trimestre."),
            ],
        )
        _pseudonymize_extraction(eleve, _identity("Dupont", "Marie"), "ELEVE_001")
        for m in eleve.matieres:
            assert "Marie" not in m.appreciation
            assert "Dupont" not in m.appreciation


# =============================================================================
# Cas limites
# =============================================================================


class TestEdgeCases:
    def test_empty_appreciation(self):
        eleve = _make_eleve("")
        _pseudonymize_extraction(eleve, _identity("Dupont", "Marie"), "ELEVE_001")
        assert eleve.matieres[0].appreciation == ""

    def test_no_name_in_text(self):
        """Un texte sans le nom de l'élève ne doit pas être modifié."""
        original = "Bon travail ce trimestre, résultats encourageants."
        eleve = _make_eleve(original)
        _pseudonymize_extraction(eleve, _identity("Dupont", "Marie"), "ELEVE_001")
        assert eleve.matieres[0].appreciation == original

    def test_word_boundary_respected(self):
        """'Marie' dans 'Mariette' ne doit PAS être remplacé."""
        eleve = _make_eleve("Mariette travaille bien.")
        _pseudonymize_extraction(eleve, _identity("Dupont", "Marie"), "ELEVE_001")
        assert "Mariette" in eleve.matieres[0].appreciation

    def test_multiple_occurrences(self):
        eleve = _make_eleve("Marie travaille bien. Marie doit aussi lire davantage.")
        _pseudonymize_extraction(eleve, _identity("Dupont", "Marie"), "ELEVE_001")
        assert eleve.matieres[0].appreciation.count("ELEVE_001") == 2
        assert "Marie" not in eleve.matieres[0].appreciation
