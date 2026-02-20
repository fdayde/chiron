"""Service de requêtes — logique de lecture partagée entre routers et cache."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def get_classe_stats(
    classe_id: str,
    trimestre: int,
    eleve_repo,
    synthese_repo,
) -> dict:
    """Calcule les statistiques agrégées d'une classe.

    Args:
        classe_id: Identifiant de la classe.
        trimestre: Numéro du trimestre.
        eleve_repo: EleveRepository.
        synthese_repo: SyntheseRepository.

    Returns:
        Dict avec classe_id, trimestre, eleve_count, et stats des synthèses.
    """
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


def get_eleves_with_syntheses(
    classe_id: str,
    trimestre: int,
    eleve_repo,
    synthese_repo,
    pseudonymizer,
) -> list[dict]:
    """Récupère les élèves avec leurs synthèses en évitant les requêtes N+1.

    Args:
        classe_id: Identifiant de la classe.
        trimestre: Numéro du trimestre.
        eleve_repo: EleveRepository.
        synthese_repo: SyntheseRepository.
        pseudonymizer: Pseudonymizer.

    Returns:
        Liste de dicts avec données élève + statut synthèse.
    """
    eleves = eleve_repo.get_by_classe(classe_id, trimestre)
    syntheses_map = synthese_repo.get_by_classe(classe_id, trimestre)
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


def get_eleve_synthese(
    eleve_id: str,
    trimestre: int,
    synthese_repo,
) -> dict:
    """Récupère la synthèse d'un élève.

    Args:
        eleve_id: Identifiant de l'élève.
        trimestre: Numéro du trimestre.
        synthese_repo: SyntheseRepository.

    Returns:
        Dict avec eleve_id, synthese_id, status, synthese (ou None).
    """
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
