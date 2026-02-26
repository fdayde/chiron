"""Tests de suppression des données RGPD (manuelle et automatique)."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

# app/ is not a package — add it to sys.path so `cache` is importable
_app_dir = str(Path(__file__).resolve().parent.parent / "app")
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

from src.core.models import (
    EleveExtraction,
    MatiereExtraction,
    SyntheseGeneree,
)
from src.storage.repositories.classe import ClasseRepository
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


@pytest.fixture()
def classe_repo(chiron_db):
    return ClasseRepository(chiron_db)


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
# Suppression trimestrielle
# =============================================================================


class TestDeleteTrimestreData:
    """Tests de la logique de suppression (sans passer par cache.py)."""

    def test_delete_eleve_and_mapping(self, pseudonymizer, eleve_repo):
        """Suppression T1 efface l'élève et son mapping privacy."""
        _ensure_classe(eleve_repo, "5A")
        eid = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        eleve_repo.create(_make_eleve(eid, "5A", 1))

        eleve_repo.delete(eid, 1)
        assert not eleve_repo.exists(eid)
        pseudonymizer.clear_mapping_for_eleve(eid)
        assert pseudonymizer.depseudonymize(eid) is None

    def test_delete_preserves_other_trimestres(self, pseudonymizer, eleve_repo):
        """Suppression T1 ne touche pas T2."""
        _ensure_classe(eleve_repo, "5A")
        eid = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        eleve_repo.create(_make_eleve(eid, "5A", 1))
        eleve_repo.create(_make_eleve(eid, "5A", 2))

        eleve_repo.delete(eid, 1)
        assert not eleve_repo.exists(eid, 1)
        assert eleve_repo.exists(eid, 2)  # T2 intact

    def test_mapping_kept_if_other_trimestre_exists(self, pseudonymizer, eleve_repo):
        """Le mapping privacy est conservé si l'élève a encore des données."""
        _ensure_classe(eleve_repo, "5A")
        eid = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        eleve_repo.create(_make_eleve(eid, "5A", 1))
        eleve_repo.create(_make_eleve(eid, "5A", 2))

        # Suppression T1: mapping must stay because T2 exists
        eleve_repo.delete(eid, 1)
        assert eleve_repo.exists(eid)  # Still has T2
        # Do NOT clear mapping
        assert pseudonymizer.depseudonymize(eid) is not None

    def test_mapping_cleared_when_no_data_remains(self, pseudonymizer, eleve_repo):
        """Le mapping est supprimé quand l'élève n'a plus aucune donnée."""
        _ensure_classe(eleve_repo, "5A")
        eid = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        eleve_repo.create(_make_eleve(eid, "5A", 1))

        # Suppression T1: no other trimester → clear mapping
        eleve_repo.delete(eid, 1)
        assert not eleve_repo.exists(eid)
        pseudonymizer.clear_mapping_for_eleve(eid)
        assert pseudonymizer.depseudonymize(eid) is None

    def test_delete_does_not_affect_other_classes(self, pseudonymizer, eleve_repo):
        """La suppression d'une classe ne touche pas les autres."""
        _ensure_classe(eleve_repo, "5A")
        _ensure_classe(eleve_repo, "5B")
        eid_a = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        eid_b = pseudonymizer.create_eleve_id("Martin", "Lucas", "5B")
        eleve_repo.create(_make_eleve(eid_a, "5A", 1))
        eleve_repo.create(_make_eleve(eid_b, "5B", 1))

        eleve_repo.delete(eid_a, 1)
        pseudonymizer.clear_mapping_for_eleve(eid_a)

        # 5B untouched
        assert eleve_repo.exists(eid_b, 1)
        assert pseudonymizer.depseudonymize(eid_b) is not None


class TestSyntheseDeletion:
    """Tests de suppression des synthèses."""

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

        deleted = synthese_repo.delete_for_eleve(eid, 1)
        assert deleted == 1
        assert synthese_repo.get_for_eleve(eid, 1) is None


# =============================================================================
# Effacement automatique — rétention (RGPD Art. 5(1)(e))
# =============================================================================


class TestAutoRetention:
    """Tests de l'effacement automatique basé sur la durée de rétention."""

    def _backdate_eleve(self, eleve_repo, eleve_id, classe_id, trimestre, days_ago):
        """Modifie created_at d'un élève pour simuler une donnée ancienne."""
        old_date = datetime.now() - timedelta(days=days_ago)
        eleve_repo._execute_write(
            "UPDATE eleves SET created_at = ? WHERE eleve_id = ? AND classe_id = ? AND trimestre = ?",
            [old_date, eleve_id, classe_id, trimestre],
        )

    def test_expired_eleves_are_deleted(
        self, pseudonymizer, eleve_repo, synthese_repo, classe_repo
    ):
        """Les élèves de plus de 30 jours sont supprimés."""
        _ensure_classe(eleve_repo, "5A")
        eid_old = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        eid_recent = pseudonymizer.create_eleve_id("Martin", "Lucas", "5A")

        eleve_repo.create(_make_eleve(eid_old, "5A", 1))
        eleve_repo.create(_make_eleve(eid_recent, "5A", 1))

        # Backdate the old one to 45 days ago
        self._backdate_eleve(eleve_repo, eid_old, "5A", 1, days_ago=45)

        with (
            patch("cache.get_eleve_repo", return_value=eleve_repo),
            patch("cache.get_synthese_repo", return_value=synthese_repo),
            patch("cache.get_classe_repo", return_value=classe_repo),
            patch("cache.get_pseudonymizer", return_value=pseudonymizer),
        ):
            from cache import auto_delete_expired_data

            result = auto_delete_expired_data(retention_days=30)

        assert result["total_eleves"] == 1
        assert not eleve_repo.exists(eid_old, 1)
        assert eleve_repo.exists(eid_recent, 1)

    def test_recent_eleves_are_kept(
        self, pseudonymizer, eleve_repo, synthese_repo, classe_repo
    ):
        """Les élèves récents ne sont pas supprimés."""
        _ensure_classe(eleve_repo, "5A")
        eid = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        eleve_repo.create(_make_eleve(eid, "5A", 1))

        with (
            patch("cache.get_eleve_repo", return_value=eleve_repo),
            patch("cache.get_synthese_repo", return_value=synthese_repo),
            patch("cache.get_classe_repo", return_value=classe_repo),
            patch("cache.get_pseudonymizer", return_value=pseudonymizer),
        ):
            from cache import auto_delete_expired_data

            result = auto_delete_expired_data(retention_days=30)

        assert result["total_eleves"] == 0
        assert eleve_repo.exists(eid, 1)

    def test_syntheses_deleted_with_expired_eleves(
        self, pseudonymizer, eleve_repo, synthese_repo, classe_repo
    ):
        """Les synthèses des élèves expirés sont également supprimées."""
        _ensure_classe(eleve_repo, "5A")
        eid = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        eleve_repo.create(_make_eleve(eid, "5A", 1))
        synthese_repo.create(
            eleve_id=eid,
            synthese=_make_synthese(),
            trimestre=1,
            metadata={"llm_provider": "test", "llm_model": "test"},
        )

        self._backdate_eleve(eleve_repo, eid, "5A", 1, days_ago=45)

        with (
            patch("cache.get_eleve_repo", return_value=eleve_repo),
            patch("cache.get_synthese_repo", return_value=synthese_repo),
            patch("cache.get_classe_repo", return_value=classe_repo),
            patch("cache.get_pseudonymizer", return_value=pseudonymizer),
        ):
            from cache import auto_delete_expired_data

            result = auto_delete_expired_data(retention_days=30)

        assert result["total_eleves"] == 1
        assert result["total_syntheses"] == 1
        assert synthese_repo.get_for_eleve(eid, 1) is None

    def test_privacy_mappings_cleaned(
        self, pseudonymizer, eleve_repo, synthese_repo, classe_repo
    ):
        """Les mappings privacy sont nettoyés quand l'élève n'a plus de données."""
        _ensure_classe(eleve_repo, "5A")
        eid = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        eleve_repo.create(_make_eleve(eid, "5A", 1))

        self._backdate_eleve(eleve_repo, eid, "5A", 1, days_ago=45)

        assert pseudonymizer.depseudonymize(eid) is not None

        with (
            patch("cache.get_eleve_repo", return_value=eleve_repo),
            patch("cache.get_synthese_repo", return_value=synthese_repo),
            patch("cache.get_classe_repo", return_value=classe_repo),
            patch("cache.get_pseudonymizer", return_value=pseudonymizer),
        ):
            from cache import auto_delete_expired_data

            result = auto_delete_expired_data(retention_days=30)

        assert result["total_mappings"] >= 1
        assert pseudonymizer.depseudonymize(eid) is None

    def test_empty_classes_deleted(
        self, pseudonymizer, eleve_repo, synthese_repo, classe_repo
    ):
        """Les classes vides après suppression sont supprimées."""
        _ensure_classe(eleve_repo, "5A")
        eid = pseudonymizer.create_eleve_id("Dupont", "Marie", "5A")
        eleve_repo.create(_make_eleve(eid, "5A", 1))

        self._backdate_eleve(eleve_repo, eid, "5A", 1, days_ago=45)

        with (
            patch("cache.get_eleve_repo", return_value=eleve_repo),
            patch("cache.get_synthese_repo", return_value=synthese_repo),
            patch("cache.get_classe_repo", return_value=classe_repo),
            patch("cache.get_pseudonymizer", return_value=pseudonymizer),
        ):
            from cache import auto_delete_expired_data

            result = auto_delete_expired_data(retention_days=30)

        assert "5A" in result["deleted_classes"]
        assert classe_repo.get("5A") is None
