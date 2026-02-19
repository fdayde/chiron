"""Cache layer pour NiceGUI (remplace @st.cache_data / @st.cache_resource).

En mode NiceGUI, l'API et l'UI tournent dans le même process.
Les appels HTTP à soi-même deadlockent l'event loop asyncio.
→ On appelle les services et repositories directement (pas de réseau).
"""

from __future__ import annotations

import dataclasses
import logging
import threading

from cachetools import TTLCache, cached

from src.api.dependencies import (
    get_classe_repo,
    get_eleve_repo,
    get_pseudonymizer,
    get_synthese_generator,
    get_synthese_repo,
)
from src.llm.config import settings as llm_settings
from src.services.query_service import (
    get_classe_stats as _get_classe_stats,
)
from src.services.query_service import (
    get_eleve_synthese as _get_eleve_synthese,
)
from src.services.query_service import (
    get_eleves_with_syntheses as _get_eleves_with_syntheses,
)
from src.services.shared import ensure_classe_exists, temp_pdf_file
from src.services.synthese_service import (
    generate_batch as _generate_batch,
)
from src.services.synthese_service import (
    generate_single as _generate_single,
)

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
        classe = classe_repo.get(classe_id)
        if not classe:
            return None

        return _get_classe_stats(
            classe_id=classe_id,
            trimestre=trimestre,
            eleve_repo=get_eleve_repo(),
            synthese_repo=get_synthese_repo(),
        )
    except Exception:
        logger.exception("Error fetching classe stats")
        return None


@cached(_eleves_cache, lock=_lock)
def fetch_eleves_with_syntheses(classe_id: str, trimestre: int) -> list[dict]:
    """Récupère les élèves avec synthèses (cache 30s)."""
    return _get_eleves_with_syntheses(
        classe_id=classe_id,
        trimestre=trimestre,
        eleve_repo=get_eleve_repo(),
        synthese_repo=get_synthese_repo(),
        pseudonymizer=get_pseudonymizer(),
    )


@cached(_eleve_cache, lock=_lock)
def fetch_eleve(eleve_id: str) -> dict | None:
    """Récupère un élève par ID (cache 30s)."""
    repo = get_eleve_repo()
    e = repo.get(eleve_id)
    return e.model_dump() if e else None


def fetch_eleve_depseudo(eleve_id: str, classe_id: str) -> dict | None:
    """Récupère un élève avec appréciations dépseudonymisées."""
    data = fetch_eleve(eleve_id)
    if not data:
        return None
    pseudonymizer = get_pseudonymizer()
    for matiere in data.get("matieres", []):
        appr = matiere.get("appreciation")
        if appr:
            matiere["appreciation"] = pseudonymizer.depseudonymize_text(appr, classe_id)
    return data


@cached(_eleve_synthese_cache, lock=_lock)
def fetch_eleve_synthese(eleve_id: str, trimestre: int) -> dict:
    """Récupère la synthèse d'un élève (cache 30s)."""
    return _get_eleve_synthese(
        eleve_id=eleve_id,
        trimestre=trimestre,
        synthese_repo=get_synthese_repo(),
    )


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
    """Importe un PDF directement (sans passer par HTTP)."""
    from src.api.routers.exports import _import_single_pdf

    classe_repo = get_classe_repo()
    eleve_repo = get_eleve_repo()
    synthese_repo = get_synthese_repo()
    pseudonymizer = get_pseudonymizer()

    ensure_classe_exists(classe_repo, classe_id)

    with temp_pdf_file(content) as tmp_path:
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


def debug_pdf_direct(content: bytes) -> bytes:
    """Génère un PDF annoté avec les zones détectées (debug)."""
    from src.document.debug_visualizer import generate_debug_pdf

    with temp_pdf_file(content) as tmp_path:
        return generate_debug_pdf(tmp_path)


def delete_eleve_direct(eleve_id: str, trimestre: int) -> None:
    """Supprime un eleve, ses syntheses, et son mapping privacy si plus aucune donnée."""
    eleve_repo = get_eleve_repo()
    synthese_repo = get_synthese_repo()
    synthese_repo.delete_for_eleve(eleve_id, trimestre)
    eleve_repo.delete(eleve_id, trimestre)

    # RGPD: nettoyer le mapping privacy si l'élève n'a plus aucun trimestre
    if not eleve_repo.exists(eleve_id):
        pseudonymizer = get_pseudonymizer()
        deleted = pseudonymizer.clear_mapping_for_eleve(eleve_id)
        if deleted:
            logger.info("Privacy mapping cleared for %s (no remaining data)", eleve_id)


def purge_trimestre(classe_id: str, trimestre: int) -> dict:
    """Purge toutes les données d'un trimestre pour une classe (RGPD).

    Supprime les élèves, synthèses, et mappings privacy (si l'élève
    n'a plus de données dans aucun autre trimestre).

    Args:
        classe_id: Identifiant de la classe.
        trimestre: Numéro du trimestre à purger.

    Returns:
        Dict avec le nombre d'éléments supprimés.
    """
    eleve_repo = get_eleve_repo()
    synthese_repo = get_synthese_repo()
    pseudonymizer = get_pseudonymizer()

    eleves = eleve_repo.get_by_classe(classe_id, trimestre)
    deleted_eleves = 0
    deleted_syntheses = 0
    deleted_mappings = 0

    for eleve in eleves:
        deleted_syntheses += synthese_repo.delete_for_eleve(eleve.eleve_id, trimestre)
        eleve_repo.delete(eleve.eleve_id, trimestre)
        deleted_eleves += 1

        # Nettoyer le mapping privacy si l'élève n'a plus aucune donnée
        if not eleve_repo.exists(eleve.eleve_id):
            deleted_mappings += pseudonymizer.clear_mapping_for_eleve(eleve.eleve_id)

    clear_eleves_cache()

    logger.info(
        "Purge T%d classe %s: %d élèves, %d synthèses, %d mappings supprimés",
        trimestre,
        classe_id,
        deleted_eleves,
        deleted_syntheses,
        deleted_mappings,
    )

    return {
        "classe_id": classe_id,
        "trimestre": trimestre,
        "deleted_eleves": deleted_eleves,
        "deleted_syntheses": deleted_syntheses,
        "deleted_mappings": deleted_mappings,
    }


def delete_classe_direct(classe_id: str) -> dict:
    """Supprime une classe et toutes ses données (élèves, synthèses, mappings)."""
    eleve_repo = get_eleve_repo()
    synthese_repo = get_synthese_repo()
    classe_repo = get_classe_repo()
    pseudonymizer = get_pseudonymizer()

    deleted_eleves = 0
    deleted_syntheses = 0
    for trimestre in [1, 2, 3]:
        eleves = eleve_repo.get_by_classe(classe_id, trimestre)
        for eleve in eleves:
            deleted_syntheses += synthese_repo.delete_for_eleve(
                eleve.eleve_id, trimestre
            )
            eleve_repo.delete(eleve.eleve_id, trimestre)
            deleted_eleves += 1

    pseudonymizer.clear_mappings(classe_id)
    classe_repo.delete(classe_id)

    logger.info(
        "Classe %s supprimée: %d élèves, %d synthèses",
        classe_id,
        deleted_eleves,
        deleted_syntheses,
    )

    return {
        "classe_id": classe_id,
        "deleted_eleves": deleted_eleves,
        "deleted_syntheses": deleted_syntheses,
    }


def clear_eleves_cache() -> None:
    """Vide les caches liés aux élèves."""
    _eleves_cache.clear()
    _eleve_cache.clear()
    _eleve_synthese_cache.clear()


def clear_classes_cache() -> None:
    """Vide le cache des classes."""
    _classes_cache.clear()


# --- Few-shot ---


def toggle_fewshot_example_direct(synthese_id: str, is_example: bool) -> bool:
    """Toggle the few-shot example flag on a synthesis."""
    logger.info("Few-shot toggle: %s → %s", synthese_id, is_example)
    synthese_repo = get_synthese_repo()
    result = synthese_repo.toggle_fewshot_example(synthese_id, is_example)
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


# --- Génération ---


def generate_synthese_direct(
    eleve_id: str,
    trimestre: int,
    provider: str = llm_settings.default_provider,
    model: str | None = None,
) -> dict:
    """Génère une synthèse pour un élève."""
    return _generate_single(
        eleve_id=eleve_id,
        trimestre=trimestre,
        eleve_repo=get_eleve_repo(),
        synthese_repo=get_synthese_repo(),
        pseudonymizer=get_pseudonymizer(),
        generator=get_synthese_generator(provider=provider, model=model),
        provider=provider,
        model=model,
        use_fewshot=True,
    )


async def generate_batch_direct(
    classe_id: str,
    trimestre: int,
    eleve_ids: list[str] | None = None,
    provider: str = llm_settings.default_provider,
    model: str | None = None,
) -> dict:
    """Génère des synthèses en batch."""
    return await _generate_batch(
        classe_id=classe_id,
        trimestre=trimestre,
        eleve_repo=get_eleve_repo(),
        synthese_repo=get_synthese_repo(),
        pseudonymizer=get_pseudonymizer(),
        generator=get_synthese_generator(provider=provider, model=model),
        provider=provider,
        model=model,
        eleve_ids=eleve_ids,
        use_fewshot=True,
    )


def update_synthese_direct(synthese_id: str, synthese_texte: str) -> None:
    """Met à jour le texte d'une synthèse."""
    synthese_repo = get_synthese_repo()
    synthese_repo.update(synthese_id, synthese_texte=synthese_texte, status="edited")


def validate_synthese_direct(synthese_id: str) -> None:
    """Valide une synthèse."""
    synthese_repo = get_synthese_repo()
    synthese_repo.update_status(synthese_id, "validated")


def delete_synthese_direct(synthese_id: str) -> None:
    """Supprime une synthèse."""
    synthese_repo = get_synthese_repo()
    synthese_repo.delete(synthese_id)
