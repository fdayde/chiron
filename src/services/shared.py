"""Helpers partagés entre services, routers et cache."""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path

from src.generation.prompt_builder import format_eleve_data
from src.generation.prompts import CURRENT_PROMPT, get_prompt_hash
from src.llm.config import settings as llm_settings

VALID_PROVIDERS = ("openai", "anthropic", "mistral")
VALID_TRIMESTRES = (1, 2, 3)


def build_llm_metadata(
    llm_metadata: dict,
    provider: str,
    model: str | None,
    generator_model: str,
    duration_ms: int,
    eleve_data_str: str,
    temperature: float = llm_settings.default_temperature,
) -> dict:
    """Construit le dict de métadonnées LLM pour stockage en base.

    Args:
        llm_metadata: Métadonnées brutes retournées par le LLM.
        provider: Provider LLM utilisé.
        model: Modèle demandé (None = défaut).
        generator_model: Modèle effectif du générateur.
        duration_ms: Durée de l'appel en ms.
        eleve_data_str: Données élève formatées (pour le prompt hash).
        temperature: Température utilisée.

    Returns:
        Dict prêt pour synthese_repo.create().
    """
    prompt_hash = get_prompt_hash(CURRENT_PROMPT, eleve_data_str)

    return {
        "llm_provider": llm_metadata.get("llm_provider", provider),
        "llm_model": llm_metadata.get("llm_model", model or generator_model),
        "llm_response_raw": llm_metadata.get("llm_response_raw"),
        "prompt_template": CURRENT_PROMPT,
        "prompt_hash": prompt_hash,
        "tokens_input": llm_metadata.get("tokens_input"),
        "tokens_output": llm_metadata.get("tokens_output"),
        "tokens_total": llm_metadata.get("tokens_total"),
        "llm_cost": llm_metadata.get("cost_usd"),
        "llm_duration_ms": duration_ms,
        "llm_temperature": temperature,
        "retry_count": llm_metadata.get("retry_count", 1),
    }


def build_eleve_data_str(eleve) -> str:
    """Formate les données élève pour le prompt hash."""
    return format_eleve_data(eleve)


@contextmanager
def temp_pdf_file(content: bytes):
    """Context manager pour écrire un PDF dans un fichier temporaire.

    Yields:
        Path vers le fichier temporaire.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        yield tmp_path
    finally:
        tmp_path.unlink(missing_ok=True)


def ensure_classe_exists(classe_repo, classe_id: str) -> None:
    """Crée la classe si elle n'existe pas encore.

    Args:
        classe_repo: ClasseRepository instance.
        classe_id: Identifiant de la classe.
    """
    from src.storage.repositories.classe import Classe

    classe = classe_repo.get(classe_id)
    if not classe:
        classe = Classe(classe_id=classe_id, nom=classe_id)
        classe_repo.create(classe)
