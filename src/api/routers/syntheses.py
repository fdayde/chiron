"""Router des synthèses."""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from src.api.dependencies import (
    get_eleve_repo,
    get_or_404,
    get_pseudonymizer,
    get_synthese_generator,
    get_synthese_repo,
)
from src.core.models import Alerte, Reussite
from src.generation.prompt_builder import format_eleve_data
from src.generation.prompts import CURRENT_PROMPT, get_prompt_hash
from src.llm.config import settings as llm_settings
from src.privacy.pseudonymizer import Pseudonymizer
from src.storage.repositories.eleve import EleveRepository
from src.storage.repositories.synthese import SyntheseRepository

logger = logging.getLogger(__name__)

router = APIRouter()


class GenerateRequest(BaseModel):
    """Modèle de requête pour générer une synthèse."""

    eleve_id: str
    trimestre: int
    provider: str = "openai"
    model: str | None = None
    temperature: float = llm_settings.default_temperature

    @field_validator("trimestre")
    @classmethod
    def validate_trimestre(cls, v: int) -> int:
        """Valide que le trimestre est 1, 2 ou 3."""
        if v not in (1, 2, 3):
            raise ValueError("trimestre must be 1, 2, or 3")
        return v

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Valide que la température est entre 0 et 2."""
        if not 0.0 <= v <= 2.0:
            raise ValueError("temperature must be between 0.0 and 2.0")
        return v

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Valide que le provider est supporté."""
        valid_providers = ("openai", "anthropic", "mistral")
        if v.lower() not in valid_providers:
            raise ValueError(f"provider must be one of: {', '.join(valid_providers)}")
        return v.lower()


class SyntheseUpdate(BaseModel):
    """Modèle de requête pour modifier une synthèse."""

    synthese_texte: str | None = None
    alertes: list[dict] | None = None
    reussites: list[dict] | None = None


class ValidateRequest(BaseModel):
    """Modèle de requête pour valider une synthèse."""

    validated_by: str | None = None


@router.post("/generate")
def generate_synthese(
    data: GenerateRequest,
    eleve_repo: EleveRepository = Depends(get_eleve_repo),
    synthese_repo: SyntheseRepository = Depends(get_synthese_repo),
    pseudonymizer: Pseudonymizer = Depends(get_pseudonymizer),
):
    """Générer une synthèse pour un élève via LLM.

    Args:
        data: Requête avec eleve_id, trimestre et config LLM optionnelle.

    Returns:
        ID de la synthèse générée et métadonnées.

    Raises:
        HTTPException: 404 si élève non trouvé, 500 en cas d'erreur de génération.
    """
    # 1. Fetch student data for the specific trimester
    eleve = get_or_404(eleve_repo, data.eleve_id, data.trimestre, entity_name="Student")

    # 2. Create generator with requested provider/model
    generator = get_synthese_generator(
        provider=data.provider,
        model=data.model,
    )

    # 3. Generate synthesis with metadata
    logger.info(
        f"Generating synthesis for {data.eleve_id} T{data.trimestre} "
        f"via {data.provider}/{data.model or 'default'}"
    )

    start_time = time.perf_counter()
    try:
        result = generator.generate_with_metadata(
            eleve=eleve,
            max_tokens=llm_settings.synthese_max_tokens,
        )
        synthese = result.synthese
        llm_metadata = result.metadata
    except Exception as e:
        logger.error(f"Generation failed for {data.eleve_id}: {e}", exc_info=True)
        from src.core.exceptions import ConfigurationError

        if isinstance(e, ConfigurationError):
            raise HTTPException(status_code=500, detail=str(e)) from e
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la génération de la synthèse. Consultez les logs du serveur.",
        ) from e

    duration_ms = int((time.perf_counter() - start_time) * 1000)

    # 3b. Depseudonymize synthesis text (replace ELEVE_XXX with real name)
    classe_id = eleve.classe
    if classe_id:
        synthese.synthese_texte = pseudonymizer.depseudonymize_text(
            synthese.synthese_texte, classe_id
        )

    # 4. Delete existing synthesis for this eleve/trimestre (allows regeneration)
    deleted_count = synthese_repo.delete_for_eleve(data.eleve_id, data.trimestre)
    if deleted_count > 0:
        logger.info(
            f"Deleted {deleted_count} existing synthesis for {data.eleve_id} T{data.trimestre}"
        )

    # 5. Prepare metadata for storage
    # Get prompt hash for traceability
    eleve_data_str = format_eleve_data(eleve)
    prompt_hash = get_prompt_hash(CURRENT_PROMPT, eleve_data_str)

    metadata = {
        "llm_provider": llm_metadata.get("llm_provider", data.provider),
        "llm_model": llm_metadata.get("llm_model", data.model or generator.model),
        "llm_response_raw": llm_metadata.get("llm_response_raw"),
        "prompt_template": CURRENT_PROMPT,
        "prompt_hash": prompt_hash,
        "tokens_input": llm_metadata.get("tokens_input"),
        "tokens_output": llm_metadata.get("tokens_output"),
        "tokens_total": llm_metadata.get("tokens_total"),
        "llm_cost": llm_metadata.get("cost_usd"),
        "llm_duration_ms": duration_ms,
        "llm_temperature": data.temperature,
        "retry_count": llm_metadata.get("retry_count", 1),
    }

    # 6. Store synthesis
    synthese_id = synthese_repo.create(
        eleve_id=data.eleve_id,
        synthese=synthese,
        trimestre=data.trimestre,
        metadata=metadata,
    )

    logger.info(
        f"Synthesis {synthese_id} created for {data.eleve_id} "
        f"({duration_ms}ms, {len(synthese.synthese_texte)} chars)"
    )

    return {
        "synthese_id": synthese_id,
        "eleve_id": data.eleve_id,
        "trimestre": data.trimestre,
        "status": "generated",
        "synthese": {
            "texte": synthese.synthese_texte,
            "alertes": [a.model_dump() for a in synthese.alertes],
            "reussites": [r.model_dump() for r in synthese.reussites],
            "posture_generale": synthese.posture_generale,
            "axes_travail": synthese.axes_travail,
        },
        "metadata": {
            "provider": metadata["llm_provider"],
            "model": metadata["llm_model"],
            "duration_ms": duration_ms,
            "tokens_input": metadata.get("tokens_input"),
            "tokens_output": metadata.get("tokens_output"),
            "tokens_total": metadata.get("tokens_total"),
            "prompt_template": CURRENT_PROMPT,
        },
    }


@router.patch("/{synthese_id}")
def update_synthese(
    synthese_id: str,
    data: SyntheseUpdate,
    synthese_repo: SyntheseRepository = Depends(get_synthese_repo),
):
    """Modifier une synthèse."""
    get_or_404(synthese_repo, synthese_id, entity_name="Synthesis")

    updates = {}
    if data.synthese_texte is not None:
        updates["synthese_texte"] = data.synthese_texte
        updates["status"] = "edited"
    if data.alertes is not None:
        updates["alertes"] = [Alerte(**a) for a in data.alertes]
    if data.reussites is not None:
        updates["reussites"] = [Reussite(**r) for r in data.reussites]

    if updates:
        synthese_repo.update(synthese_id, **updates)

    return {"status": "updated", "synthese_id": synthese_id}


@router.post("/{synthese_id}/validate")
def validate_synthese(
    synthese_id: str,
    data: ValidateRequest,
    synthese_repo: SyntheseRepository = Depends(get_synthese_repo),
):
    """Valider une synthèse."""
    get_or_404(synthese_repo, synthese_id, entity_name="Synthesis")

    synthese_repo.update_status(synthese_id, "validated", data.validated_by)
    return {"status": "validated", "synthese_id": synthese_id}


@router.get("/pending")
def get_pending_syntheses(
    classe_id: str | None = None,
    synthese_repo: SyntheseRepository = Depends(get_synthese_repo),
):
    """Récupérer toutes les synthèses en attente de validation."""
    pending = synthese_repo.get_pending(classe_id)
    return {"pending": pending, "count": len(pending)}


@router.delete("/{synthese_id}")
def delete_synthese(
    synthese_id: str,
    synthese_repo: SyntheseRepository = Depends(get_synthese_repo),
):
    """Supprimer une synthèse."""
    get_or_404(synthese_repo, synthese_id, entity_name="Synthesis")
    synthese_repo.delete(synthese_id)
    return {"status": "deleted", "synthese_id": synthese_id}
