"""Fixtures partagées pour les tests Chiron."""

from __future__ import annotations

import pytest

from src.privacy.pseudonymizer import Pseudonymizer


@pytest.fixture(autouse=True)
def _mock_flair(monkeypatch):
    """Mock flair_ner_persons → [] to avoid loading the ~500 Mo model in tests."""
    monkeypatch.setattr(
        "src.document.pseudonymization.flair_ner_persons",
        lambda text: [],
    )


@pytest.fixture()
def pseudonymizer(tmp_path):
    """Pseudonymizer avec DB temporaire (isolé par test)."""
    # Reset class-level singleton connection to ensure isolation
    Pseudonymizer._conn = None
    db_path = tmp_path / "test_privacy.duckdb"
    return Pseudonymizer(db_path=db_path)
