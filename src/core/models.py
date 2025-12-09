"""Schemas Pydantic pour Chiron."""

from typing import Literal

from pydantic import BaseModel, Field

# =============================================================================
# Extraction PDF (input)
# =============================================================================


class MatiereExtraction(BaseModel):
    """Données extraites pour une matière."""

    nom: str
    moyenne_eleve: float | None = None
    moyenne_classe: float | None = None
    appreciation: str = ""


class EleveExtraction(BaseModel):
    """Données extraites pour un élève (depuis PDF bulletin)."""

    eleve_id: str | None = None  # Généré après pseudonymisation
    nom: str | None = None  # Avant pseudonymisation
    prenom: str | None = None  # Avant pseudonymisation
    genre: Literal["M", "F"] | None = None
    classe: str | None = None
    trimestre: int | None = None
    matieres: list[MatiereExtraction] = Field(default_factory=list)
    absences_demi_journees: int | None = None
    absences_justifiees: bool | None = None
    retards: int | None = None
    engagements: list[str] = Field(default_factory=list)
    appreciation_generale: str | None = None


# =============================================================================
# Ground Truth (validation)
# =============================================================================


class EleveGroundTruth(EleveExtraction):
    """Élève avec synthèse de référence (pour validation/few-shot)."""

    synthese_ground_truth: str = ""


class GroundTruthDataset(BaseModel):
    """Dataset complet de ground truth."""

    class Metadata(BaseModel):
        projet: str = "Chiron"
        description: str = ""
        classe: str = ""
        trimestre: str = ""
        nb_eleves: int = 0

    metadata: Metadata = Field(default_factory=Metadata)
    eleves: list[EleveGroundTruth] = Field(default_factory=list)


# =============================================================================
# Génération LLM (output)
# =============================================================================


class Alerte(BaseModel):
    """Une alerte sur une matière ou un comportement."""

    matiere: str
    description: str
    severite: Literal["urgent", "attention"]


class Reussite(BaseModel):
    """Une réussite dans une matière."""

    matiere: str
    description: str


class SyntheseGeneree(BaseModel):
    """Synthèse générée par le LLM avec insights."""

    synthese_texte: str
    alertes: list[Alerte] = Field(default_factory=list)
    reussites: list[Reussite] = Field(default_factory=list)
    posture_generale: Literal["actif", "passif", "perturbateur", "variable"]
    axes_travail: list[str] = Field(default_factory=list)


# =============================================================================
# Type aliases
# =============================================================================

SyntheseStatus = Literal["draft", "generated", "edited", "validated"]
