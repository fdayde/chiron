"""Classes router."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from src.api.dependencies import get_classe_repo, get_eleve_repo, get_synthese_repo
from src.core.constants import get_current_school_year
from src.storage.repositories.classe import Classe, ClasseRepository
from src.storage.repositories.eleve import EleveRepository
from src.storage.repositories.synthese import SyntheseRepository

router = APIRouter()


class ClasseCreate(BaseModel):
    """Request model for creating a class."""

    nom: str
    niveau: str | None = None
    annee_scolaire: str | None = None

    @field_validator("annee_scolaire", mode="before")
    @classmethod
    def default_annee_scolaire(cls, v: str | None) -> str:
        return v or get_current_school_year()


class ClasseResponse(BaseModel):
    """Response model for a class."""

    classe_id: str
    nom: str
    niveau: str | None
    annee_scolaire: str


@router.post("", response_model=ClasseResponse)
def create_classe(
    data: ClasseCreate,
    repo: ClasseRepository = Depends(get_classe_repo),
) -> ClasseResponse:
    """Create a new class."""
    classe = Classe(
        classe_id="",  # Will be generated
        nom=data.nom,
        niveau=data.niveau,
        annee_scolaire=data.annee_scolaire,
    )
    classe_id = repo.create(classe)
    created = repo.get(classe_id)
    if not created:
        raise HTTPException(status_code=500, detail="Failed to create class")
    return ClasseResponse(
        classe_id=created.classe_id,
        nom=created.nom,
        niveau=created.niveau,
        annee_scolaire=created.annee_scolaire,
    )


@router.get("", response_model=list[ClasseResponse])
def list_classes(
    annee_scolaire: str | None = None,
    niveau: str | None = None,
    skip: int = 0,
    limit: int = 100,
    repo: ClasseRepository = Depends(get_classe_repo),
) -> list[ClasseResponse]:
    """List all classes with optional filters and pagination.

    Args:
        annee_scolaire: Filter by school year.
        niveau: Filter by level (e.g., "5eme").
        skip: Number of records to skip (default: 0).
        limit: Maximum number of records to return (default: 100, max: 1000).
    """
    # Clamp limit to prevent excessive queries
    limit = min(max(1, limit), 1000)
    skip = max(0, skip)

    filters = {}
    if annee_scolaire:
        filters["annee_scolaire"] = annee_scolaire
    if niveau:
        filters["niveau"] = niveau

    classes = repo.list(**filters)

    # Apply pagination
    paginated = classes[skip : skip + limit]

    return [
        ClasseResponse(
            classe_id=c.classe_id,
            nom=c.nom,
            niveau=c.niveau,
            annee_scolaire=c.annee_scolaire,
        )
        for c in paginated
    ]


@router.get("/{classe_id}", response_model=ClasseResponse)
def get_classe(
    classe_id: str,
    repo: ClasseRepository = Depends(get_classe_repo),
) -> ClasseResponse:
    """Get a class by ID."""
    classe = repo.get(classe_id)
    if not classe:
        raise HTTPException(status_code=404, detail="Class not found")
    return ClasseResponse(
        classe_id=classe.classe_id,
        nom=classe.nom,
        niveau=classe.niveau,
        annee_scolaire=classe.annee_scolaire,
    )


@router.get("/{classe_id}/eleves")
def get_classe_eleves(
    classe_id: str,
    trimestre: int | None = None,
    classe_repo: ClasseRepository = Depends(get_classe_repo),
    eleve_repo: EleveRepository = Depends(get_eleve_repo),
):
    """Get all students in a class."""
    classe = classe_repo.get(classe_id)
    if not classe:
        raise HTTPException(status_code=404, detail="Class not found")

    eleves = eleve_repo.get_by_classe(classe_id, trimestre)
    return [
        {
            "eleve_id": e.eleve_id,
            "genre": e.genre,
            "trimestre": e.trimestre,
            "absences_demi_journees": e.absences_demi_journees,
            "nb_matieres": len(e.matieres),
        }
        for e in eleves
    ]


@router.get("/{classe_id}/eleves-with-syntheses")
def get_classe_eleves_with_syntheses(
    classe_id: str,
    trimestre: int,
    classe_repo: ClasseRepository = Depends(get_classe_repo),
    eleve_repo: EleveRepository = Depends(get_eleve_repo),
    synthese_repo: SyntheseRepository = Depends(get_synthese_repo),
):
    """Get all students with their syntheses in one call.

    Optimized endpoint to avoid N+1 queries in the UI.
    Returns students with embedded synthesis data.
    """
    classe = classe_repo.get(classe_id)
    if not classe:
        raise HTTPException(status_code=404, detail="Class not found")

    # Fetch all students and all syntheses in 2 queries (not N+1)
    eleves = eleve_repo.get_by_classe(classe_id, trimestre)
    syntheses_map = synthese_repo.get_by_classe(classe_id, trimestre)

    result = []
    for e in eleves:
        synth_data = syntheses_map.get(e.eleve_id)
        item = {
            "eleve_id": e.eleve_id,
            "genre": e.genre,
            "trimestre": e.trimestre,
            "absences_demi_journees": e.absences_demi_journees,
            "retards": e.retards,
            "nb_matieres": len(e.matieres),
            # Synthesis data (None if not generated)
            "synthese_id": synth_data["synthese_id"] if synth_data else None,
            "synthese_status": synth_data["status"] if synth_data else None,
            "has_synthese": synth_data is not None,
        }
        result.append(item)

    return result


@router.get("/{classe_id}/stats")
def get_classe_stats(
    classe_id: str,
    trimestre: int,
    classe_repo: ClasseRepository = Depends(get_classe_repo),
    eleve_repo: EleveRepository = Depends(get_eleve_repo),
    synthese_repo: SyntheseRepository = Depends(get_synthese_repo),
):
    """Get aggregated statistics for a class and trimester.

    Returns counts, tokens, and cost for all syntheses.
    """
    classe = classe_repo.get(classe_id)
    if not classe:
        raise HTTPException(status_code=404, detail="Class not found")

    # Get student count
    eleves = eleve_repo.get_by_classe(classe_id, trimestre)
    eleve_count = len(eleves)

    # Get synthesis stats
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


@router.delete("/{classe_id}")
def delete_classe(
    classe_id: str,
    repo: ClasseRepository = Depends(get_classe_repo),
):
    """Delete a class."""
    classe = repo.get(classe_id)
    if not classe:
        raise HTTPException(status_code=404, detail="Class not found")
    repo.delete(classe_id)
    return {"status": "deleted", "classe_id": classe_id}
