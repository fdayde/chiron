"""Cache layer pour NiceGUI (remplace @st.cache_data / @st.cache_resource).

En mode NiceGUI, l'API et l'UI tournent dans le même process.
Les appels HTTP à soi-même deadlockent l'event loop asyncio.
→ On appelle les repositories directement (pas de réseau).

Pour les pages qui ont besoin du client HTTP (ex: appels explicites
depuis les callbacks utilisateur), on garde get_api_client().
"""

from __future__ import annotations

import dataclasses
import logging
import threading

from cachetools import TTLCache, cached

from src.api.dependencies import (
    get_classe_repo,
    get_eleve_repo,
    get_synthese_repo,
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

    eleves = eleve_repo.get_by_classe(classe_id, trimestre)
    result = []

    for eleve in eleves:
        eleve_dict = dataclasses.asdict(eleve)
        synthese = synthese_repo.get_by_eleve(eleve.eleve_id, trimestre)
        if synthese:
            eleve_dict["has_synthese"] = True
            eleve_dict["synthese_status"] = synthese.status
            eleve_dict["synthese_id"] = synthese.synthese_id
        else:
            eleve_dict["has_synthese"] = False
            eleve_dict["synthese_status"] = None
            eleve_dict["synthese_id"] = None
        result.append(eleve_dict)

    return result


@cached(_eleve_cache, lock=_lock)
def fetch_eleve(eleve_id: str) -> dict | None:
    """Récupère un élève par ID (cache 30s)."""
    repo = get_eleve_repo()
    e = repo.get(eleve_id)
    return dataclasses.asdict(e) if e else None


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


def clear_eleves_cache() -> None:
    """Vide les caches liés aux élèves."""
    _eleves_cache.clear()
    _eleve_cache.clear()
    _eleve_synthese_cache.clear()


def clear_classes_cache() -> None:
    """Vide le cache des classes."""
    _classes_cache.clear()
