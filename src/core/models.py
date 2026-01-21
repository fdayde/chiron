"""Schemas Pydantic pour Chiron."""

from typing import Literal

from pydantic import BaseModel, Field

# =============================================================================
# Extraction PDF (input)
# =============================================================================


class MatiereExtraction(BaseModel):
    """Données extraites pour une matière.

    Structure alignée sur le format PRONOTE :
    - Matière avec nom du professeur
    - Moyennes élève/classe (globales et écrit/oral pour langues)
    - Compétences travaillées durant la période
    - Appréciation du professeur
    """

    nom: str
    professeur: str | None = None  # "Mme AJENJO", "M. WOLFF"

    # Moyennes globales
    moyenne_eleve: float | None = None
    moyenne_classe: float | None = None

    # Moyennes détaillées (langues)
    note_ecrit: float | None = None
    note_oral: float | None = None
    moyenne_ecrit_classe: float | None = None
    moyenne_oral_classe: float | None = None

    # Compétences travaillées (éléments du programme)
    competences: list[str] = Field(default_factory=list)

    # Appréciation du professeur de la matière
    appreciation: str = ""


class EleveExtraction(BaseModel):
    """Données extraites pour un élève (depuis PDF bulletin).

    Structure alignée sur le format PRONOTE complet :
    - Identité et classe
    - Matières avec notes et appréciations
    - Engagements (délégué, éco-délégué...)
    - Parcours éducatifs
    - Absences et retards (en bas du bulletin)
    - Appréciation générale (synthèse du PP - ground truth)
    """

    # Identité
    eleve_id: str | None = None  # Généré après pseudonymisation
    nom: str | None = None  # Avant pseudonymisation
    prenom: str | None = None  # Avant pseudonymisation
    genre: Literal["Fille", "Garçon"] | None = None

    # Contexte scolaire
    etablissement: str | None = None
    classe: str | None = None
    trimestre: int | None = None
    annee_scolaire: str | None = None  # "2024-2025"

    # Résultats par matière
    matieres: list[MatiereExtraction] = Field(default_factory=list)

    # Moyenne générale du bulletin
    moyenne_generale: float | None = None

    # Engagements et responsabilités
    engagements: list[str] = Field(default_factory=list)  # ["Délégué(e) titulaire"]

    # Parcours éducatifs (PRONOTE)
    parcours: list[str] = Field(
        default_factory=list
    )  # ["Parcours éducatifs", "Parcours citoyen"]

    # Événements datés
    evenements: list[str] = Field(
        default_factory=list
    )  # ["06/11/2025 : DELEGUE DE CLASSE"]

    # Absences et retards (section footer du bulletin)
    absences_demi_journees: int | None = None
    absences_justifiees: bool | None = None
    retards: int | None = None

    # Appréciation générale du PP (= synthèse à générer, sert de ground truth)
    # Note: Ce champ ne sera PAS présent dans les PDFs réels à parser
    appreciation_generale: str | None = None

    # Données brutes extraites du PDF (pour post-traitement)
    raw_text: str | None = None
    raw_tables: list | None = None


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
