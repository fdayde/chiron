"""Cache layer pour NiceGUI (remplace @st.cache_data / @st.cache_resource).

En mode NiceGUI, l'API et l'UI tournent dans le même process.
Les appels HTTP à soi-même deadlockent l'event loop asyncio.
→ On appelle les repositories directement (pas de réseau).
"""

from __future__ import annotations

import dataclasses
import logging
import threading
import time

from cachetools import TTLCache, cached

from src.api.dependencies import (
    get_classe_repo,
    get_eleve_repo,
    get_pseudonymizer,
    get_synthese_generator,
    get_synthese_repo,
)
from src.generation.prompt_builder import build_fewshot_examples, format_eleve_data
from src.generation.prompts import CURRENT_PROMPT, get_prompt_hash
from src.llm.config import settings as llm_settings

logger = logging.getLogger(__name__)

# --- Caches avec TTL (remplacent @st.cache_data) ---

_lock = threading.Lock()

_classes_cache = TTLCache(maxsize=32, ttl=60)
_classe_cache = TTLCache(maxsize=32, ttl=60)
_classe_stats_cache = TTLCache(maxsize=64, ttl=30)
_eleves_cache = TTLCache(maxsize=64, ttl=30)
_eleve_cache = TTLCache(maxsize=128, ttl=30)
_eleve_synthese_cache = TTLCache(maxsize=128, ttl=30)


def check_api_health() -> bool:
    """Toujours True en mode NiceGUI (même process)."""
    return True


@cached(_classes_cache, lock=_lock)
def fetch_classes() -> list[dict]:
    """Liste toutes les classes (cache 60s)."""
    repo = get_classe_repo()
    classes = repo.list()
    return [dataclasses.asdict(c) for c in classes]


@cached(_classe_cache, lock=_lock)
def fetch_classe(classe_id: str) -> dict | None:
    """Récupère une classe par ID (cache 60s)."""
    repo = get_classe_repo()
    c = repo.get(classe_id)
    return dataclasses.asdict(c) if c else None


@cached(_classe_stats_cache, lock=_lock)
def fetch_classe_stats(classe_id: str, trimestre: int) -> dict | None:
    """Récupère les stats d'une classe (cache 30s)."""
    try:
        classe_repo = get_classe_repo()
        eleve_repo = get_eleve_repo()
        synthese_repo = get_synthese_repo()

        classe = classe_repo.get(classe_id)
        if not classe:
            return None

        eleves = eleve_repo.get_by_classe(classe_id, trimestre)
        eleve_count = len(eleves)

        stats = synthese_repo.get_stats(classe_id, trimestre)

        return {
            "classe_id": classe_id,
            "trimestre": trimestre,
            "eleve_count": eleve_count,
            "synthese_count": stats["count"],
            "validated_count": stats["validated_count"],
            "generated_count": stats["generated_count"],
            "edited_count": stats["edited_count"],
            "tokens_input": stats["tokens_input"],
            "tokens_output": stats["tokens_output"],
            "tokens_total": stats["tokens_total"],
            "cost_usd": stats["cost_usd"],
        }
    except Exception:
        logger.exception("Error fetching classe stats")
        return None


@cached(_eleves_cache, lock=_lock)
def fetch_eleves_with_syntheses(classe_id: str, trimestre: int) -> list[dict]:
    """Récupère les élèves avec synthèses (cache 30s).

    Reproduit la logique de l'endpoint /classes/{id}/eleves-with-syntheses.
    """
    eleve_repo = get_eleve_repo()
    synthese_repo = get_synthese_repo()
    pseudonymizer = get_pseudonymizer()

    eleves = eleve_repo.get_by_classe(classe_id, trimestre)
    syntheses_map = synthese_repo.get_by_classe(classe_id, trimestre)

    # Real names from pseudonymizer
    mappings = pseudonymizer.list_mappings(classe_id)
    mappings_by_id = {m["eleve_id"]: m for m in mappings}

    result = []
    for eleve in eleves:
        mapping = mappings_by_id.get(eleve.eleve_id)
        syn_data = syntheses_map.get(eleve.eleve_id)
        item = {
            "eleve_id": eleve.eleve_id,
            "prenom": mapping["prenom_original"] if mapping else None,
            "nom": mapping["nom_original"] if mapping else None,
            "genre": eleve.genre,
            "trimestre": eleve.trimestre,
            "absences_demi_journees": eleve.absences_demi_journees,
            "retards": eleve.retards,
            "nb_matieres": len(eleve.matieres),
            "has_synthese": syn_data is not None,
            "synthese_id": syn_data["synthese_id"] if syn_data else None,
            "synthese_status": syn_data["status"] if syn_data else None,
        }
        result.append(item)

    return result


@cached(_eleve_cache, lock=_lock)
def fetch_eleve(eleve_id: str) -> dict | None:
    """Récupère un élève par ID (cache 30s)."""
    repo = get_eleve_repo()
    e = repo.get(eleve_id)
    return e.model_dump() if e else None


@cached(_eleve_synthese_cache, lock=_lock)
def fetch_eleve_synthese(eleve_id: str, trimestre: int) -> dict:
    """Récupère la synthèse d'un élève (cache 30s).

    Reproduit la logique de l'endpoint /eleves/{id}/synthese.
    """
    synthese_repo = get_synthese_repo()
    result = synthese_repo.get_for_eleve_with_metadata(eleve_id, trimestre)
    if not result:
        return {
            "eleve_id": eleve_id,
            "synthese": None,
            "synthese_id": None,
            "status": None,
        }

    synthese = result["synthese"]
    return {
        "eleve_id": eleve_id,
        "synthese_id": result["synthese_id"],
        "status": result["status"],
        "synthese": {
            "synthese_texte": synthese.synthese_texte,
            "alertes": [a.model_dump() for a in synthese.alertes],
            "reussites": [r.model_dump() for r in synthese.reussites],
            "posture_generale": synthese.posture_generale,
            "axes_travail": synthese.axes_travail,
        },
    }


def get_status_counts(eleves_data: list[dict]) -> dict:
    """Calcule les compteurs de statut à partir des données élèves."""
    total = len(eleves_data)
    with_synthese = sum(1 for e in eleves_data if e.get("has_synthese"))
    validated = sum(1 for e in eleves_data if e.get("synthese_status") == "validated")

    return {
        "total": total,
        "with_synthese": with_synthese,
        "validated": validated,
        "pending": with_synthese - validated,
        "missing": total - with_synthese,
    }


def import_pdf_direct(
    content: bytes,
    filename: str,
    classe_id: str,
    trimestre: int,
    force_overwrite: bool = True,
) -> dict:
    """Importe un PDF directement (sans passer par HTTP).

    Appelle la même logique que l'endpoint POST /import/pdf,
    mais dans le même process (pas de round-trip HTTP qui bloque le WebSocket).
    """
    import tempfile
    from pathlib import Path

    from src.api.routers.exports import _import_single_pdf
    from src.storage.repositories.classe import Classe

    classe_repo = get_classe_repo()
    eleve_repo = get_eleve_repo()
    synthese_repo = get_synthese_repo()
    pseudonymizer = get_pseudonymizer()

    # Ensure class exists
    classe = classe_repo.get(classe_id)
    if not classe:
        classe = Classe(classe_id=classe_id, nom=classe_id)
        classe_repo.create(classe)

    # Write to temp file (parsers need a file path)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        result = _import_single_pdf(
            pdf_path=tmp_path,
            classe_id=classe_id,
            trimestre=trimestre,
            pseudonymizer=pseudonymizer,
            eleve_repo=eleve_repo,
            synthese_repo=synthese_repo,
            force_overwrite=force_overwrite,
        )
        was_overwritten = result["status"] == "overwritten"
        was_skipped = result["status"] == "skipped"
        return {
            "status": "success",
            "filename": filename,
            "parsed_count": 1,
            "imported_count": 0 if was_skipped else 1,
            "overwritten_count": 1 if was_overwritten else 0,
            "skipped_count": 1 if was_skipped else 0,
            "eleve_ids": [] if was_skipped else [result["eleve_id"]],
            "overwritten_ids": [result["eleve_id"]] if was_overwritten else [],
            "skipped_ids": [result["eleve_id"]] if was_skipped else [],
            "warnings": result.get("warnings", []),
        }
    finally:
        tmp_path.unlink(missing_ok=True)


def delete_eleve_direct(eleve_id: str, trimestre: int) -> None:
    """Supprime un eleve et ses syntheses (appel direct, sans HTTP)."""
    eleve_repo = get_eleve_repo()
    synthese_repo = get_synthese_repo()
    synthese_repo.delete_for_eleve(eleve_id, trimestre)
    eleve_repo.delete(eleve_id, trimestre)


def clear_eleves_cache() -> None:
    """Vide les caches liés aux élèves."""
    _eleves_cache.clear()
    _eleve_cache.clear()
    _eleve_synthese_cache.clear()


def clear_classes_cache() -> None:
    """Vide le cache des classes."""
    _classes_cache.clear()


# --- Fonctions directes (remplacent les appels HTTP via get_api_client) ---


def toggle_fewshot_example_direct(synthese_id: str, is_example: bool) -> bool:
    """Toggle the few-shot example flag on a synthesis."""
    logger.info("Few-shot toggle: %s → %s", synthese_id, is_example)
    synthese_repo = get_synthese_repo()
    result = synthese_repo.toggle_fewshot_example(synthese_id, is_example)
    # Verify the write
    actual = synthese_repo.is_fewshot_example(synthese_id)
    logger.info("Few-shot verify: %s is_fewshot=%s", synthese_id, actual)
    return result


def fetch_fewshot_count(classe_id: str, trimestre: int) -> int:
    """Count few-shot examples for a class/trimester."""
    synthese_repo = get_synthese_repo()
    return synthese_repo.count_fewshot_examples(classe_id, trimestre)


def is_fewshot_example_direct(synthese_id: str) -> bool:
    """Check if a synthesis is a few-shot example."""
    synthese_repo = get_synthese_repo()
    return synthese_repo.is_fewshot_example(synthese_id)


def _get_fewshot_generator(
    classe_id: str,
    trimestre: int,
    provider: str,
    model: str | None,
):
    """Create a SyntheseGenerator with few-shot examples if available.

    Args:
        classe_id: Class identifier.
        trimestre: Trimester number.
        provider: LLM provider.
        model: LLM model.

    Returns:
        SyntheseGenerator (with or without few-shot).
    """
    synthese_repo = get_synthese_repo()
    raw_examples = synthese_repo.get_fewshot_examples(classe_id, trimestre)

    generator = get_synthese_generator(provider=provider, model=model)

    if raw_examples:
        examples = build_fewshot_examples(raw_examples)
        generator.set_exemples(examples)
        logger.info(
            "Few-shot: %d exemple(s) injecte(s) pour %s T%d",
            len(examples),
            classe_id,
            trimestre,
        )
    else:
        logger.info("Few-shot: aucun exemple pour %s T%d", classe_id, trimestre)

    return generator


def generate_synthese_direct(
    eleve_id: str,
    trimestre: int,
    provider: str = llm_settings.default_provider,
    model: str | None = None,
) -> dict:
    """Génère une synthèse pour un élève (appel direct, sans HTTP).

    Reproduit la logique de POST /syntheses/generate.
    """
    eleve_repo = get_eleve_repo()
    synthese_repo = get_synthese_repo()
    pseudonymizer = get_pseudonymizer()

    eleve = eleve_repo.get(eleve_id, trimestre)
    if not eleve:
        raise ValueError(f"Élève {eleve_id} T{trimestre} non trouvé")

    # Use few-shot examples if available
    classe_id = eleve.classe
    generator = _get_fewshot_generator(classe_id or "", trimestre, provider, model)

    start_time = time.perf_counter()
    result = generator.generate_with_metadata(
        eleve=eleve,
        max_tokens=llm_settings.synthese_max_tokens,
    )
    synthese = result.synthese
    llm_metadata = result.metadata
    duration_ms = int((time.perf_counter() - start_time) * 1000)

    # Depseudonymize
    classe_id = eleve.classe
    if classe_id:
        synthese.synthese_texte = pseudonymizer.depseudonymize_text(
            synthese.synthese_texte, classe_id
        )

    # Delete existing synthesis (allows regeneration)
    synthese_repo.delete_for_eleve(eleve_id, trimestre)

    # Prepare metadata
    eleve_data_str = format_eleve_data(eleve)
    prompt_hash = get_prompt_hash(CURRENT_PROMPT, eleve_data_str)

    metadata = {
        "llm_provider": llm_metadata.get("llm_provider", provider),
        "llm_model": llm_metadata.get("llm_model", model or generator.model),
        "llm_response_raw": llm_metadata.get("llm_response_raw"),
        "prompt_template": CURRENT_PROMPT,
        "prompt_hash": prompt_hash,
        "tokens_input": llm_metadata.get("tokens_input"),
        "tokens_output": llm_metadata.get("tokens_output"),
        "tokens_total": llm_metadata.get("tokens_total"),
        "llm_cost": llm_metadata.get("cost_usd"),
        "llm_duration_ms": duration_ms,
        "llm_temperature": llm_settings.default_temperature,
        "retry_count": llm_metadata.get("retry_count", 1),
    }

    synthese_id = synthese_repo.create(
        eleve_id=eleve_id,
        synthese=synthese,
        trimestre=trimestre,
        metadata=metadata,
    )

    return {
        "synthese_id": synthese_id,
        "eleve_id": eleve_id,
        "trimestre": trimestre,
        "status": "generated",
        "metadata": {
            "provider": metadata["llm_provider"],
            "model": metadata["llm_model"],
            "duration_ms": duration_ms,
            "tokens_input": metadata.get("tokens_input"),
            "tokens_output": metadata.get("tokens_output"),
            "tokens_total": metadata.get("tokens_total"),
            "cost_usd": metadata.get("llm_cost"),
        },
    }


async def generate_batch_direct(
    classe_id: str,
    trimestre: int,
    eleve_ids: list[str] | None = None,
    provider: str = llm_settings.default_provider,
    model: str | None = None,
) -> dict:
    """Génère des synthèses en batch (appel direct, sans HTTP).

    Reproduit la logique de POST /syntheses/generate-batch.
    Async car utilise generator.generate_batch_async().
    """
    eleve_repo = get_eleve_repo()
    synthese_repo = get_synthese_repo()
    pseudonymizer = get_pseudonymizer()

    all_eleves = eleve_repo.get_by_classe(classe_id, trimestre)
    if not all_eleves:
        raise ValueError(f"Aucun élève trouvé pour {classe_id} T{trimestre}")

    # Determine which students to generate for
    if eleve_ids is not None:
        eleves_map = {e.eleve_id: e for e in all_eleves}
        eleves_to_generate = []
        for eid in eleve_ids:
            if eid in eleves_map:
                eleves_to_generate.append(eleves_map[eid])
                synthese_repo.delete_for_eleve(eid, trimestre)
    else:
        syntheses_map = synthese_repo.get_by_classe(classe_id, trimestre)
        eleves_to_generate = [e for e in all_eleves if e.eleve_id not in syntheses_map]

    if not eleves_to_generate:
        return {
            "classe_id": classe_id,
            "trimestre": trimestre,
            "total_requested": 0,
            "total_success": 0,
            "total_errors": 0,
            "duration_ms": 0,
        }

    generator = _get_fewshot_generator(classe_id, trimestre, provider, model)

    start_time = time.perf_counter()
    gen_results = await generator.generate_batch_async(
        eleves=eleves_to_generate,
        max_tokens=llm_settings.synthese_max_tokens,
    )
    total_duration_ms = int((time.perf_counter() - start_time) * 1000)

    total_success = 0
    total_errors = 0

    for eleve, gen_result in zip(eleves_to_generate, gen_results, strict=False):
        if gen_result is None:
            total_errors += 1
            continue

        synthese = gen_result.synthese
        llm_metadata = gen_result.metadata

        # Depseudonymize
        eleve_classe_id = eleve.classe
        if eleve_classe_id:
            synthese.synthese_texte = pseudonymizer.depseudonymize_text(
                synthese.synthese_texte, eleve_classe_id
            )

        # Prepare metadata
        eleve_data_str = format_eleve_data(eleve)
        prompt_hash = get_prompt_hash(CURRENT_PROMPT, eleve_data_str)

        metadata = {
            "llm_provider": llm_metadata.get("llm_provider", provider),
            "llm_model": llm_metadata.get("llm_model", model or generator.model),
            "llm_response_raw": llm_metadata.get("llm_response_raw"),
            "prompt_template": CURRENT_PROMPT,
            "prompt_hash": prompt_hash,
            "tokens_input": llm_metadata.get("tokens_input"),
            "tokens_output": llm_metadata.get("tokens_output"),
            "tokens_total": llm_metadata.get("tokens_total"),
            "llm_cost": llm_metadata.get("cost_usd"),
            "llm_duration_ms": total_duration_ms // len(eleves_to_generate),
            "llm_temperature": llm_settings.default_temperature,
            "retry_count": llm_metadata.get("retry_count", 1),
        }

        synthese_repo.create(
            eleve_id=eleve.eleve_id,
            synthese=synthese,
            trimestre=trimestre,
            metadata=metadata,
        )
        total_success += 1

    logger.info(
        f"Batch generation: {total_success}/{len(eleves_to_generate)} succès "
        f"en {total_duration_ms}ms"
    )

    return {
        "classe_id": classe_id,
        "trimestre": trimestre,
        "total_requested": len(eleves_to_generate),
        "total_success": total_success,
        "total_errors": total_errors,
        "duration_ms": total_duration_ms,
    }


def update_synthese_direct(synthese_id: str, synthese_texte: str) -> None:
    """Met à jour le texte d'une synthèse (appel direct, sans HTTP)."""
    synthese_repo = get_synthese_repo()
    synthese_repo.update(synthese_id, synthese_texte=synthese_texte, status="edited")


def validate_synthese_direct(synthese_id: str) -> None:
    """Valide une synthèse (appel direct, sans HTTP)."""
    synthese_repo = get_synthese_repo()
    synthese_repo.update_status(synthese_id, "validated")


def delete_synthese_direct(synthese_id: str) -> None:
    """Supprime une synthèse (appel direct, sans HTTP)."""
    synthese_repo = get_synthese_repo()
    synthese_repo.delete(synthese_id)
