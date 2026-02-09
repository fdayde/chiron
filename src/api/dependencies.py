"""Injection de dépendances FastAPI."""

from functools import lru_cache

from fastapi import HTTPException

from src.generation.generator import SyntheseGenerator
from src.llm.config import settings as llm_settings
from src.privacy.pseudonymizer import Pseudonymizer
from src.storage.repositories.classe import ClasseRepository
from src.storage.repositories.eleve import EleveRepository
from src.storage.repositories.synthese import SyntheseRepository


@lru_cache
def get_classe_repo() -> ClasseRepository:
    """Singleton ClasseRepository."""
    return ClasseRepository()


@lru_cache
def get_eleve_repo() -> EleveRepository:
    """Singleton EleveRepository."""
    return EleveRepository()


@lru_cache
def get_synthese_repo() -> SyntheseRepository:
    """Singleton SyntheseRepository."""
    return SyntheseRepository()


@lru_cache
def get_pseudonymizer() -> Pseudonymizer:
    """Singleton Pseudonymizer."""
    return Pseudonymizer()


def get_or_404(repo, *args, entity_name: str = "Resource"):
    """Récupère une entité ou lève une 404.

    Args:
        repo: Repository avec une méthode get().
        *args: Arguments positionnels passés à repo.get().
        entity_name: Nom pour le message d'erreur.

    Returns:
        L'entité trouvée.

    Raises:
        HTTPException: 404 si non trouvée.
    """
    entity = repo.get(*args)
    if not entity:
        raise HTTPException(status_code=404, detail=f"{entity_name} not found")
    return entity


def get_synthese_generator(
    provider: str = llm_settings.default_provider,
    model: str | None = None,
) -> SyntheseGenerator:
    """Instance de SyntheseGenerator (non cachée car provider/model varient).

    Args:
        provider: Provider LLM (openai, anthropic, mistral).
        model: Nom du modèle (None = défaut du provider).

    Returns:
        Instance configurée de SyntheseGenerator.
    """
    return SyntheseGenerator(provider=provider, model=model)
