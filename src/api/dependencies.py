"""Dependency injection for FastAPI."""

from functools import lru_cache

from src.privacy.pseudonymizer import Pseudonymizer
from src.storage.repositories.classe import ClasseRepository
from src.storage.repositories.eleve import EleveRepository
from src.storage.repositories.synthese import SyntheseRepository


@lru_cache
def get_classe_repo() -> ClasseRepository:
    """Get ClasseRepository singleton."""
    return ClasseRepository()


@lru_cache
def get_eleve_repo() -> EleveRepository:
    """Get EleveRepository singleton."""
    return EleveRepository()


@lru_cache
def get_synthese_repo() -> SyntheseRepository:
    """Get SyntheseRepository singleton."""
    return SyntheseRepository()


@lru_cache
def get_pseudonymizer() -> Pseudonymizer:
    """Get Pseudonymizer singleton."""
    return Pseudonymizer()
