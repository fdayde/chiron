"""Classes router."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import get_classe_repo, get_eleve_repo
from src.storage.repositories.classe import Classe, ClasseRepository
from src.storage.repositories.eleve import EleveRepository

router = APIRouter()


class ClasseCreate(BaseModel):
    """Request model for creating a class."""

    nom: str
    niveau: str | None = None
    annee_scolaire: str = "2024-2025"


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
    repo: ClasseRepository = Depends(get_classe_repo),
) -> list[ClasseResponse]:
    """List all classes with optional filters."""
    filters = {}
    if annee_scolaire:
        filters["annee_scolaire"] = annee_scolaire
    if niveau:
        filters["niveau"] = niveau

    classes = repo.list(**filters)
    return [
        ClasseResponse(
            classe_id=c.classe_id,
            nom=c.nom,
            niveau=c.niveau,
            annee_scolaire=c.annee_scolaire,
        )
        for c in classes
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
