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


class Insight(BaseModel):
    """Un insight détecté (alerte, réussite, etc.)."""

    type: Literal["alerte", "reussite", "engagement", "posture", "ecart"]
    description: str
    matieres: list[str] | None = None
    severite: Literal["info", "attention", "urgent"] | None = None


class SyntheseGeneree(BaseModel):
    """Synthèse générée par le LLM."""

    synthese_texte: str
    alertes: list[Insight] = Field(default_factory=list)
    reussites: list[Insight] = Field(default_factory=list)
    engagement_differencie: dict[str, str] = Field(default_factory=dict)
    posture_generale: Literal["actif", "passif", "perturbateur", "variable"] | None = (
        None
    )
    ecart_effort_resultat: (
        Literal["equilibre", "effort_sup_resultat", "resultat_sup_effort"] | None
    ) = None


# =============================================================================
# Type aliases
# =============================================================================

SyntheseStatus = Literal["draft", "generated", "edited", "validated"]
