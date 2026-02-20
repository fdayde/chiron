"""Tests du Pseudonymizer — code privacy-critical RGPD."""

from __future__ import annotations

import pytest

from src.core.exceptions import PrivacyError

# =============================================================================
# Création de mappings
# =============================================================================


class TestCreateEleveId:
    def test_basic_creation(self, pseudonymizer):
        eid = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        assert eid.startswith("ELEVE_")
        assert eid == "ELEVE_001"

    def test_idempotent(self, pseudonymizer):
        eid1 = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        eid2 = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        assert eid1 == eid2

    def test_idempotent_case_insensitive(self, pseudonymizer):
        eid1 = pseudonymizer.create_eleve_id("DUPONT", "Marie", "5A")
        eid2 = pseudonymizer.create_eleve_id("dupont", "marie", "5A")
        assert eid1 == eid2

    def test_idempotent_extra_spaces(self, pseudonymizer):
        eid1 = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        eid2 = pseudonymizer.create_eleve_id("  Dupont  ", "  Marie  ", "5A")
        assert eid1 == eid2

    def test_different_students_get_different_ids(self, pseudonymizer):
        eid1 = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        eid2 = pseudonymizer.create_eleve_id("Martin", "Lucas", "5A")
        assert eid1 != eid2

    def test_same_name_different_class(self, pseudonymizer):
        eid1 = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        eid2 = pseudonymizer.create_eleve_id("Dupont", "Marie", "5B")
        assert eid1 != eid2

    def test_accented_names(self, pseudonymizer):
        eid = pseudonymizer.create_eleve_id("Béziat", "Héloïse", "5A")
        assert eid.startswith("ELEVE_")
        # Idempotent avec accents
        eid2 = pseudonymizer.create_eleve_id("Béziat", "Héloïse", "5A")
        assert eid == eid2

    def test_composed_name(self, pseudonymizer):
        eid = pseudonymizer.create_eleve_id("De La Fontaine", "Jean-Pierre", "5A")
        assert eid.startswith("ELEVE_")

    def test_empty_nom_raises(self, pseudonymizer):
        with pytest.raises(PrivacyError, match="nom is required"):
            pseudonymizer.create_eleve_id("", "Marie", "5A")

    def test_none_prenom_allowed(self, pseudonymizer):
        eid = pseudonymizer.create_eleve_id("Dupont", None, "5A")
        assert eid.startswith("ELEVE_")

    def test_sequential_ids(self, pseudonymizer):
        """Les IDs sont séquentiels au sein d'un pseudonymizer frais."""
        eid1 = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        eid2 = pseudonymizer.create_eleve_id("Martin", "Lucas", "5A")
        eid3 = pseudonymizer.create_eleve_id("Petit", "Emma", "5A")
        # Extract numeric suffixes and check ordering
        nums = [int(e.replace("ELEVE_", "")) for e in [eid1, eid2, eid3]]
        assert nums[0] < nums[1] < nums[2]


# =============================================================================
# Dépseudonymisation
# =============================================================================


class TestDepseudonymize:
    def test_basic_depseudonymize(self, pseudonymizer):
        eid = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        result = pseudonymizer.depseudonymize(eid)
        assert result is not None
        assert result["nom_original"] == "Dupont"
        assert result["prenom_original"] == "Marie"
        assert result["classe_id"] == "5A"

    def test_depseudonymize_unknown_id(self, pseudonymizer):
        result = pseudonymizer.depseudonymize("ELEVE_999")
        assert result is None

    def test_depseudonymize_text_basic(self, pseudonymizer):
        pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        text = "ELEVE_001 a bien travaillé ce trimestre."
        result = pseudonymizer.depseudonymize_text(text, classe_id="5A")
        assert "Marie" in result
        assert "ELEVE_001" not in result

    def test_depseudonymize_text_scoped_by_classe(self, pseudonymizer):
        """La dépseudonymisation scopée ne résout pas les IDs d'autres classes."""
        pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        pseudonymizer.create_eleve_id("Martin", "Lucas", "5B")
        text = "ELEVE_001 et ELEVE_002 sont dans la même cour."
        # Scoped to 5A: only ELEVE_001 (Marie) should be resolved
        result = pseudonymizer.depseudonymize_text(text, classe_id="5A")
        assert "Marie" in result
        assert "ELEVE_002" in result  # Not resolved (belongs to 5B)


# =============================================================================
# Suppression de mappings
# =============================================================================


class TestClearMappings:
    def test_clear_mapping_for_eleve(self, pseudonymizer):
        eid = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        deleted = pseudonymizer.clear_mapping_for_eleve(eid)
        assert deleted == 1
        assert pseudonymizer.depseudonymize(eid) is None

    def test_clear_mapping_for_unknown_eleve(self, pseudonymizer):
        deleted = pseudonymizer.clear_mapping_for_eleve("ELEVE_999")
        assert deleted == 0

    def test_clear_mappings_by_classe(self, pseudonymizer):
        pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        pseudonymizer.create_eleve_id("Martin", "Lucas", "5A")
        pseudonymizer.create_eleve_id("Petit", "Emma", "5B")
        deleted = pseudonymizer.clear_mappings(classe_id="5A")
        assert deleted == 2
        # 5B untouched
        assert pseudonymizer.depseudonymize("ELEVE_003") is not None

    def test_clear_all_mappings(self, pseudonymizer):
        pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        pseudonymizer.create_eleve_id("Martin", "Lucas", "5B")
        deleted = pseudonymizer.clear_mappings()
        assert deleted == 2
        assert pseudonymizer.list_mappings() == []

    def test_list_mappings_by_classe(self, pseudonymizer):
        pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        pseudonymizer.create_eleve_id("Martin", "Lucas", "5B")
        mappings_a = pseudonymizer.list_mappings(classe_id="5A")
        assert len(mappings_a) == 1
        assert mappings_a[0]["nom_original"] == "Dupont"
