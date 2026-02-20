"""Router des synthèses."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from src.api.dependencies import (
    get_eleve_repo,
    get_or_404,
    get_pseudonymizer,
    get_synthese_generator,
    get_synthese_repo,
)
from src.core.models import Alerte, Reussite
from src.generation.prompts import CURRENT_PROMPT, get_prompt, get_prompt_hash
from src.llm.config import settings as llm_settings
from src.privacy.pseudonymizer import Pseudonymizer
from src.services.shared import VALID_PROVIDERS, VALID_TRIMESTRES
from src.services.synthese_service import generate_batch as _generate_batch
from src.services.synthese_service import generate_single as _generate_single
from src.storage.repositories.eleve import EleveRepository
from src.storage.repositories.synthese import SyntheseRepository

logger = logging.getLogger(__name__)

router = APIRouter()


def _validate_trimestre(v: int) -> int:
    """Valide que le trimestre est 1, 2 ou 3."""
    if v not in VALID_TRIMESTRES:
        raise ValueError("trimestre must be 1, 2, or 3")
    return v


def _validate_provider(v: str) -> str:
    """Valide que le provider est supporté."""
    if v.lower() not in VALID_PROVIDERS:
        raise ValueError(f"provider must be one of: {', '.join(VALID_PROVIDERS)}")
    return v.lower()


class GenerateRequest(BaseModel):
    """Modèle de requête pour générer une synthèse."""

    eleve_id: str
    trimestre: int
    provider: str = llm_settings.default_provider
    model: str | None = None
    temperature: float = llm_settings.default_temperature

    @field_validator("trimestre")
    @classmethod
    def validate_trimestre(cls, v: int) -> int:
        return _validate_trimestre(v)

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
        return _validate_provider(v)


class SyntheseUpdate(BaseModel):
    """Modèle de requête pour modifier une synthèse."""

    synthese_texte: str | None = None
    alertes: list[dict] | None = None
    reussites: list[dict] | None = None


class ValidateRequest(BaseModel):
    """Modèle de requête pour valider une synthèse."""

    validated_by: str | None = None


class GenerateBatchRequest(BaseModel):
    """Modèle de requête pour la génération batch."""

    classe_id: str
    trimestre: int
    eleve_ids: list[str] | None = Field(
        default=None,
        description="IDs des élèves à générer. Si None, génère pour tous les manquants.",
    )
    provider: str = llm_settings.default_provider
    model: str | None = None

    @field_validator("trimestre")
    @classmethod
    def validate_trimestre(cls, v: int) -> int:
        return _validate_trimestre(v)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        return _validate_provider(v)


@router.post("/generate")
def generate_synthese(
    data: GenerateRequest,
    eleve_repo: EleveRepository = Depends(get_eleve_repo),
    synthese_repo: SyntheseRepository = Depends(get_synthese_repo),
    pseudonymizer: Pseudonymizer = Depends(get_pseudonymizer),
):
    """Générer une synthèse pour un élève via LLM."""
    # Verify student exists
    get_or_404(eleve_repo, data.eleve_id, data.trimestre, entity_name="Student")

    generator = get_synthese_generator(provider=data.provider, model=data.model)

    try:
        return _generate_single(
            eleve_id=data.eleve_id,
            trimestre=data.trimestre,
            eleve_repo=eleve_repo,
            synthese_repo=synthese_repo,
            pseudonymizer=pseudonymizer,
            generator=generator,
            provider=data.provider,
            model=data.model,
            use_fewshot=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Generation failed for {data.eleve_id}: {e}", exc_info=True)
        from src.core.exceptions import ConfigurationError

        if isinstance(e, ConfigurationError):
            raise HTTPException(status_code=500, detail=str(e)) from e
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la génération de la synthèse. Consultez les logs du serveur.",
        ) from e


@router.post("/generate-batch")
async def generate_batch(
    data: GenerateBatchRequest,
    eleve_repo: EleveRepository = Depends(get_eleve_repo),
    synthese_repo: SyntheseRepository = Depends(get_synthese_repo),
    pseudonymizer: Pseudonymizer = Depends(get_pseudonymizer),
):
    """Générer des synthèses pour plusieurs élèves en parallèle."""
    generator = get_synthese_generator(provider=data.provider, model=data.model)

    try:
        return await _generate_batch(
            classe_id=data.classe_id,
            trimestre=data.trimestre,
            eleve_repo=eleve_repo,
            synthese_repo=synthese_repo,
            pseudonymizer=pseudonymizer,
            generator=generator,
            provider=data.provider,
            model=data.model,
            eleve_ids=data.eleve_ids,
            use_fewshot=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/prompts/current")
def get_current_prompt():
    """Retourne le prompt actuellement utilisé pour la génération."""
    template = get_prompt(CURRENT_PROMPT)
    return {
        "name": CURRENT_PROMPT,
        "version": template["version"],
        "description": template.get("description", ""),
        "system_prompt": template["system"],
        "user_prompt_template": template["user"],
        "prompt_hash": get_prompt_hash(CURRENT_PROMPT),
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
