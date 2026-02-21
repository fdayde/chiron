"""Construction des prompts pour la génération de synthèses."""

import json

from src.core.models import EleveExtraction, EleveGroundTruth, MatiereExtraction
from src.generation.prompts import CURRENT_PROMPT, get_prompt

# Max characters for synthesis text in few-shot examples
FEWSHOT_SYNTHESE_MAX_CHARS = 1000

# Échelle de maîtrise du socle commun (LSU)
LSU_LEVELS = [
    (8.0, "Maîtrise insuffisante"),
    (12.0, "Maîtrise fragile"),
    (16.0, "Maîtrise satisfaisante"),
    (float("inf"), "Très bonne maîtrise"),
]


def _note_to_lsu(note: float) -> str:
    """Convertit une note /20 en niveau de maîtrise LSU."""
    for seuil, label in LSU_LEVELS:
        if note < seuil:
            return label
    return LSU_LEVELS[-1][1]


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

    # Matières
    lines.append("\nRÉSULTATS PAR MATIÈRE :")
    lines.append("-" * 40)

    for m in eleve.matieres:
        lines.append(format_matiere(m))

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
        parts.append(f" : {_note_to_lsu(matiere.moyenne_eleve)}")

    if matiere.appreciation:
        parts.append(f'\n  "{matiere.appreciation}"')

    return "".join(parts)


def _truncate_appreciation(appreciation: str) -> str:
    """Truncate an appreciation to its first sentence for few-shot examples.

    Args:
        appreciation: Full teacher appreciation text.

    Returns:
        First sentence only.
    """
    if not appreciation:
        return ""
    # Split on sentence-ending punctuation followed by space
    for end in [". ", "! ", "? "]:
        idx = appreciation.find(end)
        if idx != -1:
            return appreciation[: idx + 1]
    return appreciation


def build_fewshot_examples(raw_examples: list[dict]) -> list[EleveGroundTruth]:
    """Build EleveGroundTruth objects from DB rows for few-shot injection.

    Truncates appreciations to 1 sentence and synthesis to FEWSHOT_SYNTHESE_MAX_CHARS.

    Args:
        raw_examples: List of dicts from SyntheseRepository.get_fewshot_examples().

    Returns:
        List of EleveGroundTruth ready for PromptBuilder.
    """
    results = []
    for row in raw_examples:
        # Parse matieres JSON
        matieres_raw = row.get("matieres")
        if isinstance(matieres_raw, str):
            matieres_raw = json.loads(matieres_raw)
        matieres_raw = matieres_raw or []

        matieres = []
        for m in matieres_raw:
            mat = MatiereExtraction(**m)
            # Truncate appreciation to first sentence
            mat.appreciation = _truncate_appreciation(mat.appreciation)
            matieres.append(mat)

        # Truncate synthesis text
        synthese_texte = row.get("synthese_texte", "")
        if len(synthese_texte) > FEWSHOT_SYNTHESE_MAX_CHARS:
            synthese_texte = synthese_texte[:FEWSHOT_SYNTHESE_MAX_CHARS] + "..."

        example = EleveGroundTruth(
            eleve_id=row["eleve_id"],
            genre=row.get("genre"),
            matieres=matieres,
            synthese_ground_truth=synthese_texte,
        )
        results.append(example)

    return results


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

        # Get prompts from centralized prompts.py
        prompt_template = get_prompt(CURRENT_PROMPT)
        system_content = prompt_template["system"]
        user_template = prompt_template["user"]

        if classe_info:
            system_content += f"\n\nCONTEXTE CLASSE :\n{classe_info}"

        messages.append({"role": "system", "content": system_content})

        # Few-shot examples — wrap in JSON format matching the expected output
        for exemple in self.exemples:
            messages.append(
                {
                    "role": "user",
                    "content": user_template.format(
                        eleve_data=format_eleve_data(exemple)
                    ),
                }
            )
            # Wrap the ground truth text in the expected JSON structure
            # so the model learns both the style AND the output format
            fewshot_response = json.dumps(
                {
                    "synthese_texte": exemple.synthese_ground_truth,
                    "alertes": [],
                    "reussites": [],
                    "axes_travail": [],
                    "biais_detectes": [],
                },
                ensure_ascii=False,
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": fewshot_response,
                }
            )

        # Élève cible
        messages.append(
            {
                "role": "user",
                "content": user_template.format(eleve_data=format_eleve_data(eleve)),
            }
        )

        return messages
