"""Service de génération de synthèses — logique métier partagée."""

from __future__ import annotations

import logging
import re
import time

from src.generation.prompt_builder import build_fewshot_examples, format_eleve_data
from src.llm.config import settings as llm_settings
from src.services.shared import build_llm_metadata

logger = logging.getLogger(__name__)


def get_fewshot_generator(
    classe_id: str,
    trimestre: int,
    provider: str,
    model: str | None,
    synthese_repo,
    pseudonymizer,
    generator,
):
    """Configure un générateur avec les exemples few-shot si disponibles.

    Charge les exemples validés, re-pseudonymise les textes (car la DB
    stocke les noms réels après dépseudonymisation), puis les injecte
    dans le générateur.

    Args:
        classe_id: Identifiant de la classe.
        trimestre: Numéro du trimestre.
        provider: Provider LLM.
        model: Modèle LLM.
        synthese_repo: SyntheseRepository instance.
        pseudonymizer: Pseudonymizer instance.
        generator: SyntheseGenerator instance.

    Returns:
        Le générateur (modifié in-place avec les exemples few-shot).
    """
    raw_examples = synthese_repo.get_fewshot_examples(classe_id, trimestre)

    if raw_examples:
        # Re-pseudonymize synthese_texte before sending to LLM
        # (DB stores real names after depseudonymization)
        mappings = pseudonymizer.list_mappings(classe_id)
        for row in raw_examples:
            texte = row.get("synthese_texte", "")
            if texte:
                texte = _re_pseudonymize_text(texte, mappings)
                row["synthese_texte"] = texte

        examples = build_fewshot_examples(raw_examples)
        generator.set_exemples(examples)
        logger.info(
            "Few-shot: %d exemple(s) re-pseudonymise(s) et injecte(s) pour %s T%d",
            len(examples),
            classe_id,
            trimestre,
        )
    else:
        logger.info("Few-shot: aucun exemple pour %s T%d", classe_id, trimestre)

    return generator


def _re_pseudonymize_text(texte: str, mappings: list[dict]) -> str:
    """Remplace les noms réels par les identifiants pseudonymes dans un texte.

    Args:
        texte: Texte contenant potentiellement des noms réels.
        mappings: Liste des mappings pseudonymisation.

    Returns:
        Texte avec noms remplacés par ELEVE_XXX.
    """
    for m in mappings:
        eid = m["eleve_id"]
        nom = m.get("nom_original", "")
        prenom = m.get("prenom_original", "")
        if prenom and nom:
            texte = re.sub(
                rf"\b{re.escape(prenom)}\s+{re.escape(nom)}\b",
                eid,
                texte,
                flags=re.IGNORECASE,
            )
            texte = re.sub(
                rf"\b{re.escape(nom)}\s+{re.escape(prenom)}\b",
                eid,
                texte,
                flags=re.IGNORECASE,
            )
        if nom:
            texte = re.sub(
                rf"\b{re.escape(nom)}\b",
                eid,
                texte,
                flags=re.IGNORECASE,
            )
        if prenom:
            texte = re.sub(
                rf"\b{re.escape(prenom)}\b",
                eid,
                texte,
                flags=re.IGNORECASE,
            )
    return texte


def persist_synthese(
    eleve,
    synthese,
    llm_metadata: dict,
    provider: str,
    model: str | None,
    generator_model: str,
    duration_ms: int,
    trimestre: int,
    pseudonymizer,
    synthese_repo,
    temperature: float = llm_settings.default_temperature,
) -> str:
    """Dépseudonymise, prépare les métadonnées et stocke une synthèse.

    Pipeline post-génération partagé entre generate_single et generate_batch.

    Args:
        eleve: EleveExtraction de l'élève.
        synthese: SyntheseGeneree du LLM.
        llm_metadata: Métadonnées brutes du LLM.
        provider: Provider LLM.
        model: Modèle demandé.
        generator_model: Modèle effectif du générateur.
        duration_ms: Durée de l'appel en ms.
        trimestre: Numéro du trimestre.
        pseudonymizer: Pseudonymizer instance.
        synthese_repo: SyntheseRepository instance.
        temperature: Température utilisée.

    Returns:
        synthese_id créé.
    """
    # Depseudonymize
    classe_id = eleve.classe
    if classe_id:
        synthese.synthese_texte = pseudonymizer.depseudonymize_text(
            synthese.synthese_texte, classe_id
        )

    # Delete existing synthesis (allows regeneration)
    synthese_repo.delete_for_eleve(eleve.eleve_id, trimestre)

    # Build metadata
    eleve_data_str = format_eleve_data(eleve)
    metadata = build_llm_metadata(
        llm_metadata=llm_metadata,
        provider=provider,
        model=model,
        generator_model=generator_model,
        duration_ms=duration_ms,
        eleve_data_str=eleve_data_str,
        temperature=temperature,
    )

    # Store
    return synthese_repo.create(
        eleve_id=eleve.eleve_id,
        synthese=synthese,
        trimestre=trimestre,
        metadata=metadata,
    )


def generate_single(
    eleve_id: str,
    trimestre: int,
    eleve_repo,
    synthese_repo,
    pseudonymizer,
    generator,
    provider: str,
    model: str | None,
    use_fewshot: bool = True,
) -> dict:
    """Génère une synthèse pour un élève.

    Args:
        eleve_id: Identifiant de l'élève.
        trimestre: Numéro du trimestre.
        eleve_repo: EleveRepository.
        synthese_repo: SyntheseRepository.
        pseudonymizer: Pseudonymizer.
        generator: SyntheseGenerator.
        provider: Provider LLM.
        model: Modèle LLM.
        use_fewshot: Si True, charge les exemples few-shot.

    Returns:
        Dict avec synthese_id, eleve_id, trimestre, status, metadata.
    """
    eleve = eleve_repo.get(eleve_id, trimestre)
    if not eleve:
        raise ValueError(f"Élève {eleve_id} T{trimestre} non trouvé")

    classe_id = eleve.classe or ""

    if use_fewshot:
        get_fewshot_generator(
            classe_id,
            trimestre,
            provider,
            model,
            synthese_repo,
            pseudonymizer,
            generator,
        )

    start_time = time.perf_counter()
    result = generator.generate_with_metadata(
        eleve=eleve,
        max_tokens=llm_settings.synthese_max_tokens,
    )
    duration_ms = int((time.perf_counter() - start_time) * 1000)

    synthese_id = persist_synthese(
        eleve=eleve,
        synthese=result.synthese,
        llm_metadata=result.metadata,
        provider=provider,
        model=model,
        generator_model=generator.model,
        duration_ms=duration_ms,
        trimestre=trimestre,
        pseudonymizer=pseudonymizer,
        synthese_repo=synthese_repo,
    )

    return {
        "synthese_id": synthese_id,
        "eleve_id": eleve_id,
        "trimestre": trimestre,
        "status": "generated",
        "metadata": {
            "provider": result.metadata.get("llm_provider", provider),
            "model": result.metadata.get("llm_model", model or generator.model),
            "duration_ms": duration_ms,
            "tokens_input": result.metadata.get("tokens_input"),
            "tokens_output": result.metadata.get("tokens_output"),
            "tokens_total": result.metadata.get("tokens_total"),
            "cost_usd": result.metadata.get("cost_usd"),
        },
    }


async def generate_batch(
    classe_id: str,
    trimestre: int,
    eleve_repo,
    synthese_repo,
    pseudonymizer,
    generator,
    provider: str,
    model: str | None,
    eleve_ids: list[str] | None = None,
    use_fewshot: bool = True,
) -> dict:
    """Génère des synthèses en batch.

    Args:
        classe_id: Identifiant de la classe.
        trimestre: Numéro du trimestre.
        eleve_repo: EleveRepository.
        synthese_repo: SyntheseRepository.
        pseudonymizer: Pseudonymizer.
        generator: SyntheseGenerator.
        provider: Provider LLM.
        model: Modèle LLM.
        eleve_ids: Liste explicite d'IDs (None = tous les manquants).
        use_fewshot: Si True, charge les exemples few-shot.

    Returns:
        Dict avec classe_id, trimestre, total_requested, total_success, total_errors, duration_ms, results.
    """
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
            "results": [],
        }

    if use_fewshot:
        get_fewshot_generator(
            classe_id,
            trimestre,
            provider,
            model,
            synthese_repo,
            pseudonymizer,
            generator,
        )

    start_time = time.perf_counter()
    gen_results = await generator.generate_batch_async(
        eleves=eleves_to_generate,
        max_tokens=llm_settings.synthese_max_tokens,
    )
    total_duration_ms = int((time.perf_counter() - start_time) * 1000)

    results = []
    total_success = 0
    total_errors = 0

    for eleve, gen_result in zip(eleves_to_generate, gen_results, strict=False):
        if gen_result is None:
            total_errors += 1
            results.append(
                {
                    "eleve_id": eleve.eleve_id,
                    "status": "error",
                    "error": "Échec de la génération LLM",
                }
            )
            continue

        synthese_id = persist_synthese(
            eleve=eleve,
            synthese=gen_result.synthese,
            llm_metadata=gen_result.metadata,
            provider=provider,
            model=model,
            generator_model=generator.model,
            duration_ms=total_duration_ms // len(eleves_to_generate),
            trimestre=trimestre,
            pseudonymizer=pseudonymizer,
            synthese_repo=synthese_repo,
        )
        total_success += 1
        results.append(
            {
                "eleve_id": eleve.eleve_id,
                "status": "generated",
                "synthese_id": synthese_id,
            }
        )

    logger.info(
        "Batch generation: %d/%d succès en %dms",
        total_success,
        len(eleves_to_generate),
        total_duration_ms,
    )

    return {
        "classe_id": classe_id,
        "trimestre": trimestre,
        "total_requested": len(eleves_to_generate),
        "total_success": total_success,
        "total_errors": total_errors,
        "duration_ms": total_duration_ms,
        "results": results,
    }
