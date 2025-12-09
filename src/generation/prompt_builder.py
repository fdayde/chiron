"""Construction des prompts pour la génération de synthèses."""

from src.core.models import EleveExtraction, EleveGroundTruth, MatiereExtraction

# Template système pour le LLM
SYSTEM_PROMPT = """Tu es un assistant pour professeur principal de collège/lycée.
Ta tâche est de rédiger des synthèses trimestrielles et d'identifier les points clés pour le conseil de classe.

## ÉTAPE 1 : RÉDIGER LA SYNTHÈSE

Consignes pour la synthèse :
- Adopte le même ton et style que les exemples fournis par le professeur
- Cite les matières concernées SANS mentionner les notes chiffrées
- Identifie les points forts ET les axes d'amélioration
- Sois constructif et bienveillant
- Utilise le vouvoiement ou tutoiement selon les exemples
- Accorde correctement selon le genre de l'élève (il/elle, lui/elle)
- Longueur : 2-4 phrases, concises et percutantes
- NE CITE JAMAIS les notes exactes (ex: "12,5/20")
- N'utilise JAMAIS de point-virgule (;), préfère des phrases courtes ou des virgules

## ÉTAPE 2 : IDENTIFIER LES ALERTES

Une alerte signale un point nécessitant une attention particulière.
Critères :
- Note < 10/20 dans une matière
- Note très inférieure à la moyenne de classe (écart > 3 points)
- Comportement problématique mentionné dans les appréciations (passivité, bavardages, manque de travail)

Sévérité :
- "urgent" : note < 8 OU problème comportemental grave
- "attention" : note entre 8-10 OU écart significatif avec la classe

## ÉTAPE 3 : IDENTIFIER LES RÉUSSITES

Une réussite signale un point fort de l'élève.
Critères :
- Note > 14/20 dans une matière
- Note très supérieure à la moyenne de classe (écart > 3 points)
- Comportement positif mentionné (sérieux, participation, progrès)

## ÉTAPE 4 : DÉTERMINER LA POSTURE GÉNÉRALE

Analyse les appréciations pour déterminer la posture dominante :
- "actif" : participe, s'investit, volontaire
- "passif" : en retrait, discret, manque de participation
- "perturbateur" : bavardages, agitation, manque de concentration
- "variable" : posture qui varie selon les matières

## ÉTAPE 5 : IDENTIFIER LES AXES DE TRAVAIL

Liste 1 à 3 axes prioritaires d'amélioration (ex: "Participation orale", "Régularité du travail personnel").

## FORMAT DE RÉPONSE (JSON)

Réponds UNIQUEMENT avec un JSON valide selon cette structure :
```json
{
  "synthese_texte": "La synthèse rédigée...",
  "alertes": [
    {"matiere": "Nom matière", "description": "Description courte", "severite": "urgent|attention"}
  ],
  "reussites": [
    {"matiere": "Nom matière", "description": "Description courte"}
  ],
  "posture_generale": "actif|passif|perturbateur|variable",
  "axes_travail": ["Axe 1", "Axe 2"]
}
```"""

# JSON Schema pour la réponse (pour validation)
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "synthese_texte": {"type": "string"},
        "alertes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "matiere": {"type": "string"},
                    "description": {"type": "string"},
                    "severite": {"type": "string", "enum": ["urgent", "attention"]},
                },
                "required": ["matiere", "description", "severite"],
            },
        },
        "reussites": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "matiere": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["matiere", "description"],
            },
        },
        "posture_generale": {
            "type": "string",
            "enum": ["actif", "passif", "perturbateur", "variable"],
        },
        "axes_travail": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "synthese_texte",
        "alertes",
        "reussites",
        "posture_generale",
        "axes_travail",
    ],
}


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

    # Genre
    if eleve.genre:
        genre_str = "Fille" if eleve.genre == "F" else "Garçon"
        lines.append(f"Genre : {genre_str}")

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

        # System prompt
        system_content = SYSTEM_PROMPT
        if classe_info:
            system_content += f"\n\nCONTEXTE CLASSE :\n{classe_info}"

        messages.append({"role": "system", "content": system_content})

        # Few-shot examples
        for exemple in self.exemples:
            # User message avec données élève
            messages.append(
                {
                    "role": "user",
                    "content": f"Rédige une synthèse pour cet élève :\n\n{format_eleve_data(exemple)}",
                }
            )
            # Assistant response avec synthèse de référence
            messages.append(
                {
                    "role": "assistant",
                    "content": exemple.synthese_ground_truth,
                }
            )

        # Élève cible
        messages.append(
            {
                "role": "user",
                "content": f"Rédige une synthèse pour cet élève :\n\n{format_eleve_data(eleve)}",
            }
        )

        return messages

    def build_prompt_text(
        self,
        eleve: EleveExtraction,
        classe_info: str | None = None,
    ) -> str:
        """Construit le prompt complet sous forme de texte (pour debug).

        Args:
            eleve: Élève pour lequel générer la synthèse.
            classe_info: Info contextuelle sur la classe (optionnel).

        Returns:
            Prompt complet en texte.
        """
        messages = self.build_messages(eleve, classe_info)
        parts = []

        for msg in messages:
            role = msg["role"].upper()
            content = msg["content"]
            parts.append(f"[{role}]\n{content}\n")

        return "\n".join(parts)
