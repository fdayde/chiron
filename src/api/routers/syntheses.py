"""Syntheses router."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import get_eleve_repo, get_synthese_repo
from src.core.models import Alerte, Reussite, SyntheseGeneree
from src.storage.repositories.eleve import EleveRepository
from src.storage.repositories.synthese import SyntheseRepository

router = APIRouter()


class GenerateRequest(BaseModel):
    """Request model for generating a synthesis."""

    eleve_id: str
    trimestre: int


class SyntheseUpdate(BaseModel):
    """Request model for updating a synthesis."""

    synthese_texte: str | None = None
    alertes: list[dict] | None = None
    reussites: list[dict] | None = None


class ValidateRequest(BaseModel):
    """Request model for validating a synthesis."""

    validated_by: str | None = None


@router.post("/generate")
def generate_synthese(
    data: GenerateRequest,
    eleve_repo: EleveRepository = Depends(get_eleve_repo),
    synthese_repo: SyntheseRepository = Depends(get_synthese_repo),
):
    """Generate a synthesis for a student.

    Note: This is a placeholder. In production, this would call the LLM generator.
    """
    eleve = eleve_repo.get(data.eleve_id)
    if not eleve:
        raise HTTPException(status_code=404, detail="Student not found")

    # Placeholder synthesis - in production, use the LLM generator
    synthese = SyntheseGeneree(
        synthese_texte=f"Synthèse générée pour {data.eleve_id} - Trimestre {data.trimestre}",
        alertes=[],
        reussites=[],
        posture_generale="actif",
        axes_travail=[],
    )

    synthese_id = synthese_repo.create(
        eleve_id=data.eleve_id,
        synthese=synthese,
        trimestre=data.trimestre,
        metadata={"provider": "placeholder", "model": "none"},
    )

    return {
        "synthese_id": synthese_id,
        "eleve_id": data.eleve_id,
        "trimestre": data.trimestre,
        "status": "generated",
    }


@router.patch("/{synthese_id}")
def update_synthese(
    synthese_id: str,
    data: SyntheseUpdate,
    synthese_repo: SyntheseRepository = Depends(get_synthese_repo),
):
    """Update a synthesis."""
    synthese = synthese_repo.get(synthese_id)
    if not synthese:
        raise HTTPException(status_code=404, detail="Synthesis not found")

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
    """Validate a synthesis."""
    synthese = synthese_repo.get(synthese_id)
    if not synthese:
        raise HTTPException(status_code=404, detail="Synthesis not found")

    synthese_repo.update_status(synthese_id, "validated", data.validated_by)
    return {"status": "validated", "synthese_id": synthese_id}


@router.get("/pending")
def get_pending_syntheses(
    classe_id: str | None = None,
    synthese_repo: SyntheseRepository = Depends(get_synthese_repo),
):
    """Get all syntheses pending validation."""
    pending = synthese_repo.get_pending(classe_id)
    return {"pending": pending, "count": len(pending)}


@router.delete("/{synthese_id}")
def delete_synthese(
    synthese_id: str,
    synthese_repo: SyntheseRepository = Depends(get_synthese_repo),
):
    """Delete a synthesis."""
    synthese = synthese_repo.get(synthese_id)
    if not synthese:
        raise HTTPException(status_code=404, detail="Synthesis not found")
    synthese_repo.delete(synthese_id)
    return {"status": "deleted", "synthese_id": synthese_id}
