"""Tests de la purge trimestrielle RGPD."""

from __future__ import annotations

import pytest

from src.core.models import (
    EleveExtraction,
    MatiereExtraction,
    SyntheseGeneree,
)
from src.storage.repositories.eleve import EleveRepository
from src.storage.repositories.synthese import SyntheseRepository


@pytest.fixture()
def chiron_db(tmp_path):
    """DB chiron temporaire avec tables créées."""
    db_path = tmp_path / "chiron.duckdb"
    repo = EleveRepository(str(db_path))
    repo.ensure_tables()
    return str(db_path)


@pytest.fixture()
def eleve_repo(chiron_db):
    return EleveRepository(chiron_db)


@pytest.fixture()
def synthese_repo(chiron_db):
    return SyntheseRepository(chiron_db)


def _make_eleve(eleve_id: str, classe: str, trimestre: int) -> EleveExtraction:
    return EleveExtraction(
        eleve_id=eleve_id,
        classe=classe,
        trimestre=trimestre,
        matieres=[MatiereExtraction(nom="Maths", appreciation="Bon travail.")],
    )


def _make_synthese() -> SyntheseGeneree:
    return SyntheseGeneree(
        synthese_texte="Bonne élève.",
    )


def _ensure_classe(eleve_repo, classe_id: str) -> None:
    """Crée la classe si elle n'existe pas (FK constraint)."""
    try:
        eleve_repo._execute_write(
            "INSERT INTO classes (classe_id, nom) VALUES (?, ?)",
            [classe_id, classe_id],
        )
    except Exception:
        pass  # Already exists


# =============================================================================
# Purge trimestrielle
# =============================================================================


class TestPurgeTrimestre:
    """Tests de la logique de purge (sans passer par cache.py)."""

    def test_purge_deletes_eleve_and_mapping(self, pseudonymizer, eleve_repo):
        """Purge T1 supprime l'élève et son mapping privacy."""
        _ensure_classe(eleve_repo, "5A")
        eid = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        eleve_repo.create(_make_eleve(eid, "5A", 1))

        # Simulate purge
        eleve_repo.delete(eid, 1)
        assert not eleve_repo.exists(eid)
        pseudonymizer.clear_mapping_for_eleve(eid)
        assert pseudonymizer.depseudonymize(eid) is None

    def test_purge_preserves_other_trimestres(self, pseudonymizer, eleve_repo):
        """Purge T1 ne touche pas T2."""
        _ensure_classe(eleve_repo, "5A")
        eid = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        eleve_repo.create(_make_eleve(eid, "5A", 1))
        eleve_repo.create(_make_eleve(eid, "5A", 2))

        # Purge T1 only
        eleve_repo.delete(eid, 1)
        assert not eleve_repo.exists(eid, 1)
        assert eleve_repo.exists(eid, 2)  # T2 intact

    def test_mapping_kept_if_other_trimestre_exists(self, pseudonymizer, eleve_repo):
        """Le mapping privacy est conservé si l'élève a encore des données."""
        _ensure_classe(eleve_repo, "5A")
        eid = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        eleve_repo.create(_make_eleve(eid, "5A", 1))
        eleve_repo.create(_make_eleve(eid, "5A", 2))

        # Purge T1: mapping must stay because T2 exists
        eleve_repo.delete(eid, 1)
        assert eleve_repo.exists(eid)  # Still has T2
        # Do NOT clear mapping
        assert pseudonymizer.depseudonymize(eid) is not None

    def test_mapping_cleared_when_no_data_remains(self, pseudonymizer, eleve_repo):
        """Le mapping est supprimé quand l'élève n'a plus aucune donnée."""
        _ensure_classe(eleve_repo, "5A")
        eid = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        eleve_repo.create(_make_eleve(eid, "5A", 1))

        # Purge T1: no other trimester → clear mapping
        eleve_repo.delete(eid, 1)
        assert not eleve_repo.exists(eid)
        pseudonymizer.clear_mapping_for_eleve(eid)
        assert pseudonymizer.depseudonymize(eid) is None

    def test_purge_does_not_affect_other_classes(self, pseudonymizer, eleve_repo):
        """La purge d'une classe ne touche pas les autres."""
        _ensure_classe(eleve_repo, "5A")
        _ensure_classe(eleve_repo, "5B")
        eid_a = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        eid_b = pseudonymizer.create_eleve_id("Martin", "Lucas", "5B")
        eleve_repo.create(_make_eleve(eid_a, "5A", 1))
        eleve_repo.create(_make_eleve(eid_b, "5B", 1))

        # Purge 5A T1
        eleve_repo.delete(eid_a, 1)
        pseudonymizer.clear_mapping_for_eleve(eid_a)

        # 5B untouched
        assert eleve_repo.exists(eid_b, 1)
        assert pseudonymizer.depseudonymize(eid_b) is not None


class TestSyntheseDeletion:
    """Tests de suppression des synthèses lors de la purge."""

    def test_synthese_deleted_with_eleve(
        self, pseudonymizer, eleve_repo, synthese_repo
    ):
        _ensure_classe(eleve_repo, "5A")
        eid = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        eleve_repo.create(_make_eleve(eid, "5A", 1))
        synthese_repo.create(
            eleve_id=eid,
            synthese=_make_synthese(),
            trimestre=1,
            metadata={"llm_provider": "test", "llm_model": "test"},
        )
        assert synthese_repo.get_for_eleve(eid, 1) is not None

        # Purge
        deleted = synthese_repo.delete_for_eleve(eid, 1)
        assert deleted == 1
        assert synthese_repo.get_for_eleve(eid, 1) is None
