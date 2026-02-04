"""Construction des prompts pour la génération de synthèses."""

from src.core.models import EleveExtraction, EleveGroundTruth, MatiereExtraction
from src.generation.prompts import CURRENT_PROMPT, get_prompt

# Délimiteurs pour isoler les données utilisateur (prompt injection mitigation)
DATA_START = "<ELEVE_DATA>"
DATA_END = "</ELEVE_DATA>"


def format_eleve_data(eleve: EleveExtraction) -> str:
    """Formate les données d'un élève pour le prompt.

    Args:
        eleve: Données de l'élève.

    Returns:
        Texte formaté lisible.
    """
    lines = []

    # Identifiant
    if eleve.eleve_id:
        lines.append(f"Élève : {eleve.eleve_id}")

    # Genre (already in Fille/Garçon format from models.py)
    if eleve.genre:
        lines.append(f"Genre : {eleve.genre}")

    # Absences
    if eleve.absences_demi_journees is not None:
        justif = "(justifiées)" if eleve.absences_justifiees else "(non justifiées)"
        lines.append(
            f"Absences : {eleve.absences_demi_journees} demi-journées {justif}"
        )

    if eleve.retards:
        lines.append(f"Retards : {eleve.retards}")

    # Engagements
    if eleve.engagements:
        lines.append(f"Engagements : {', '.join(eleve.engagements)}")

    # Matières
    lines.append("\nRÉSULTATS PAR MATIÈRE :")
    lines.append("-" * 40)

    for m in eleve.matieres:
        lines.append(format_matiere(m))

    # Moyenne générale calculée
    notes = [m.moyenne_eleve for m in eleve.matieres if m.moyenne_eleve is not None]
    if notes:
        moy = sum(notes) / len(notes)
        lines.append(f"\nMoyenne générale : {moy:.2f}/20")

    return "\n".join(lines)


def format_matiere(matiere: MatiereExtraction) -> str:
    """Formate une matière pour le prompt.

    Args:
        matiere: Données de la matière.

    Returns:
        Ligne formatée.
    """
    parts = [f"• {matiere.nom}"]

    if matiere.moyenne_eleve is not None:
        parts.append(f": {matiere.moyenne_eleve:.2f}/20")
        if matiere.moyenne_classe is not None:
            diff = matiere.moyenne_eleve - matiere.moyenne_classe
            sign = "+" if diff >= 0 else ""
            parts.append(f" (classe: {matiere.moyenne_classe:.2f}, {sign}{diff:.2f})")

    if matiere.appreciation:
        parts.append(f'\n  "{matiere.appreciation}"')

    return "".join(parts)


class PromptBuilder:
    """Constructeur de prompts few-shot pour la génération de synthèses."""

    def __init__(self, exemples: list[EleveGroundTruth] | None = None) -> None:
        """Initialise le builder avec des exemples few-shot optionnels.

        Args:
            exemples: Liste d'élèves avec synthèses de référence pour few-shot.
        """
        self.exemples = exemples or []

    def build_messages(
        self,
        eleve: EleveExtraction,
        classe_info: str | None = None,
    ) -> list[dict[str, str]]:
        """Construit les messages pour l'appel LLM.

        Args:
            eleve: Élève pour lequel générer la synthèse.
            classe_info: Info contextuelle sur la classe (optionnel).

        Returns:
            Liste de messages au format OpenAI/Anthropic.
        """
        messages = []

        # Get system prompt from centralized prompts.py
        prompt_template = get_prompt(CURRENT_PROMPT)
        system_content = prompt_template["system"]

        if classe_info:
            system_content += f"\n\nCONTEXTE CLASSE :\n{classe_info}"

        messages.append({"role": "system", "content": system_content})

        # Few-shot examples
        for exemple in self.exemples:
            # User message avec données élève (wrapped in delimiters)
            messages.append(
                {
                    "role": "user",
                    "content": f"Rédige une synthèse pour cet élève :\n\n{DATA_START}\n{format_eleve_data(exemple)}\n{DATA_END}",
                }
            )
            # Assistant response avec synthèse de référence
            messages.append(
                {
                    "role": "assistant",
                    "content": exemple.synthese_ground_truth,
                }
            )

        # Élève cible (wrapped in delimiters for prompt injection protection)
        messages.append(
            {
                "role": "user",
                "content": f"Rédige une synthèse pour cet élève :\n\n{DATA_START}\n{format_eleve_data(eleve)}\n{DATA_END}",
            }
        )

        return messages
