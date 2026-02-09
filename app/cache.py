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

from api_client import ChironAPIClient
from cachetools import TTLCache, cached

from src.api.dependencies import (
    get_classe_repo,
    get_eleve_repo,
    get_pseudonymizer,
    get_synthese_repo,
)

logger = logging.getLogger(__name__)

# --- Singleton API client (pour les callbacks qui doivent passer par HTTP) ---

_client_instance: ChironAPIClient | None = None
_client_lock = threading.Lock()


def get_api_client() -> ChironAPIClient:
    """Retourne le client API (singleton thread-safe).

    Utilisé uniquement dans les callbacks utilisateur (boutons),
    PAS pendant le rendu de page (sinon deadlock event loop).
    """
    global _client_instance
    if _client_instance is None:
        with _client_lock:
            if _client_instance is None:
                _client_instance = ChironAPIClient()
    return _client_instance


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


def clear_eleves_cache() -> None:
    """Vide les caches liés aux élèves."""
    _eleves_cache.clear()
    _eleve_cache.clear()
    _eleve_synthese_cache.clear()


def clear_classes_cache() -> None:
    """Vide le cache des classes."""
    _classes_cache.clear()
