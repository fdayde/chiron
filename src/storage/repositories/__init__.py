"""Repository pattern implementations for data access."""

from src.storage.repositories.classe import ClasseRepository
from src.storage.repositories.eleve import EleveRepository
from src.storage.repositories.synthese import SyntheseRepository

__all__ = ["ClasseRepository", "EleveRepository", "SyntheseRepository"]
