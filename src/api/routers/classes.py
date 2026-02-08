"""Router des classes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from src.api.dependencies import (
    get_classe_repo,
    get_eleve_repo,
    get_or_404,
    get_pseudonymizer,
    get_synthese_repo,
)
from src.core.constants import get_current_school_year
from src.core.exceptions import StorageError
from src.privacy.pseudonymizer import Pseudonymizer
from src.storage.repositories.classe import Classe, ClasseRepository
from src.storage.repositories.eleve import EleveRepository
from src.storage.repositories.synthese import SyntheseRepository

router = APIRouter()


class ClasseCreate(BaseModel):
    """Modèle de requête pour créer une classe."""

    nom: str
    niveau: str | None = None
    annee_scolaire: str | None = None

    @field_validator("annee_scolaire", mode="before")
    @classmethod
    def default_annee_scolaire(cls, v: str | None) -> str:
        return v or get_current_school_year()


class ClasseResponse(BaseModel):
    """Modèle de réponse pour une classe."""

    classe_id: str
    nom: str
    niveau: str | None
    annee_scolaire: str


@router.post("", response_model=ClasseResponse)
def create_classe(
    data: ClasseCreate,
    repo: ClasseRepository = Depends(get_classe_repo),
) -> ClasseResponse:
    """Créer une nouvelle classe."""
    classe = Classe(
        classe_id="",  # Will be generated
        nom=data.nom,
        niveau=data.niveau,
        annee_scolaire=data.annee_scolaire,
    )
    try:
        classe_id = repo.create(classe)
    except StorageError as e:
        raise HTTPException(status_code=409, detail=e.message) from e
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
    """Liste les classes avec filtres et pagination optionnels.

    Args:
        annee_scolaire: Filtrer par année scolaire.
        niveau: Filtrer par niveau (ex: "5eme").
        skip: Nombre d'enregistrements à sauter (défaut: 0).
        limit: Nombre max d'enregistrements (défaut: 100, max: 1000).
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
    """Récupérer une classe par ID."""
    classe = get_or_404(repo, classe_id, entity_name="Class")
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
    """Récupérer tous les élèves d'une classe."""
    get_or_404(classe_repo, classe_id, entity_name="Class")

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
    pseudonymizer: Pseudonymizer = Depends(get_pseudonymizer),
):
    """Récupérer les élèves avec leurs synthèses en un seul appel.

    Endpoint optimisé pour éviter les requêtes N+1 côté UI.
    """
    get_or_404(classe_repo, classe_id, entity_name="Class")

    # Fetch all students and all syntheses in 2 queries (not N+1)
    eleves = eleve_repo.get_by_classe(classe_id, trimestre)
    syntheses_map = synthese_repo.get_by_classe(classe_id, trimestre)

    # Fetch all pseudonymization mappings in 1 query
    mappings = pseudonymizer.list_mappings(classe_id)
    mappings_by_id = {m["eleve_id"]: m for m in mappings}

    result = []
    for e in eleves:
        synth_data = syntheses_map.get(e.eleve_id)
        mapping = mappings_by_id.get(e.eleve_id)
        item = {
            "eleve_id": e.eleve_id,
            "prenom": mapping["prenom_original"] if mapping else None,
            "nom": mapping["nom_original"] if mapping else None,
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
    """Statistiques agrégées pour une classe et un trimestre.

    Retourne les compteurs, tokens et coûts des synthèses.
    """
    get_or_404(classe_repo, classe_id, entity_name="Class")

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
    """Supprimer une classe."""
    get_or_404(repo, classe_id, entity_name="Class")
    repo.delete(classe_id)
    return {"status": "deleted", "classe_id": classe_id}
