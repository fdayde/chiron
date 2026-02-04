"""Eleves router."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import get_eleve_repo, get_synthese_repo
from src.storage.repositories.eleve import EleveRepository
from src.storage.repositories.synthese import SyntheseRepository

router = APIRouter()


class MatiereResponse(BaseModel):
    """Response model for a subject."""

    nom: str
    professeur: str | None
    moyenne_eleve: float | None
    moyenne_classe: float | None
    appreciation: str


class EleveResponse(BaseModel):
    """Response model for a student."""

    eleve_id: str
    classe: str | None
    genre: str | None
    trimestre: int | None
    absences_demi_journees: int | None
    absences_justifiees: bool | None
    retards: int | None
    engagements: list[str]
    parcours: list[str]
    evenements: list[str]
    matieres: list[MatiereResponse]


@router.get("/{eleve_id}", response_model=EleveResponse)
def get_eleve(
    eleve_id: str,
    trimestre: int | None = None,
    repo: EleveRepository = Depends(get_eleve_repo),
) -> EleveResponse:
    """Get a student by ID and optionally trimester.

    Args:
        eleve_id: Student identifier.
        trimestre: Optional trimester. If not provided, returns latest.
    """
    eleve = repo.get(eleve_id, trimestre)
    if not eleve:
        raise HTTPException(status_code=404, detail="Student not found")

    return EleveResponse(
        eleve_id=eleve.eleve_id,
        classe=eleve.classe,
        genre=eleve.genre,
        trimestre=eleve.trimestre,
        absences_demi_journees=eleve.absences_demi_journees,
        absences_justifiees=eleve.absences_justifiees,
        retards=eleve.retards,
        engagements=eleve.engagements,
        parcours=eleve.parcours,
        evenements=eleve.evenements,
        matieres=[
            MatiereResponse(
                nom=m.nom,
                professeur=m.professeur,
                moyenne_eleve=m.moyenne_eleve,
                moyenne_classe=m.moyenne_classe,
                appreciation=m.appreciation,
            )
            for m in eleve.matieres
        ],
    )


@router.get("/{eleve_id}/synthese")
def get_eleve_synthese(
    eleve_id: str,
    trimestre: int | None = None,
    eleve_repo: EleveRepository = Depends(get_eleve_repo),
    synthese_repo: SyntheseRepository = Depends(get_synthese_repo),
):
    """Get the current synthesis for a student."""
    eleve = eleve_repo.get(eleve_id, trimestre)
    if not eleve:
        raise HTTPException(status_code=404, detail="Student not found")

    # Use eleve's trimester if not specified
    if trimestre is None:
        trimestre = eleve.trimestre

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


@router.delete("/{eleve_id}")
def delete_eleve(
    eleve_id: str,
    trimestre: int | None = None,
    repo: EleveRepository = Depends(get_eleve_repo),
):
    """Delete a student record.

    Args:
        eleve_id: Student identifier.
        trimestre: Optional trimester. If not provided, deletes ALL records for this student.
    """
    eleve = repo.get(eleve_id, trimestre)
    if not eleve:
        raise HTTPException(status_code=404, detail="Student not found")
    repo.delete(eleve_id, trimestre)

    if trimestre:
        return {"status": "deleted", "eleve_id": eleve_id, "trimestre": trimestre}
    return {"status": "deleted", "eleve_id": eleve_id, "all_trimesters": True}
