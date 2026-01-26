"""Dependency injection for FastAPI."""

from functools import lru_cache

from src.generation.generator import SyntheseGenerator
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


def get_synthese_generator(
    provider: str = "openai",
    model: str | None = None,
) -> SyntheseGenerator:
    """Get SyntheseGenerator instance.

    Note: Not cached because provider/model may vary per request.

    Args:
        provider: LLM provider (openai, anthropic, mistral).
        model: Specific model name (None = provider default).

    Returns:
        Configured SyntheseGenerator instance.
    """
    return SyntheseGenerator(provider=provider, model=model)
