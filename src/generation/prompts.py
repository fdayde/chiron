"""Templates de prompts versionnés pour la génération de synthèses.

Les prompts sont versionnés dans le code (pas en base de données) pour :
- Traçabilité avec git
- DRY (pas de duplication)
- Reproductibilité (on sait quel prompt a généré quelle synthèse)

En base, on stocke uniquement `prompt_template="synthese_v1"` + `prompt_hash`.

Usage:
    from src.generation.prompts import get_prompt, CURRENT_PROMPT

    template = get_prompt(CURRENT_PROMPT)
    system = template["system"]
    user = template["user"].format(eleve_data=data)
"""

import hashlib
import json

# ============================================================================
# TEMPLATES DE PROMPTS
# ============================================================================

PROMPT_TEMPLATES = {
    "synthese_v1": {
        "version": "1.0.0",
        "description": "Prompt initial pour génération de synthèses trimestrielles",
        "system": """Tu es un assistant pour professeur principal de collège/lycée.
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
```""",
        "user": """Rédige une synthèse pour cet élève :

{eleve_data}""",
    },
}

# Prompt actuel utilisé par défaut
CURRENT_PROMPT = "synthese_v1"


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================


def get_prompt(template_name: str | None = None) -> dict:
    """Récupère un template de prompt.

    Args:
        template_name: Nom du template. Si None, utilise CURRENT_PROMPT.

    Returns:
        Dict avec version, system, user.

    Raises:
        ValueError: Si le template n'existe pas.
    """
    name = template_name or CURRENT_PROMPT

    if name not in PROMPT_TEMPLATES:
        raise ValueError(
            f"Template '{name}' inconnu. Disponibles: {list(PROMPT_TEMPLATES.keys())}"
        )

    return PROMPT_TEMPLATES[name]


def get_prompt_hash(template_name: str | None = None, eleve_data: str = "") -> str:
    """Calcule un hash du prompt complet pour traçabilité.

    Args:
        template_name: Nom du template.
        eleve_data: Données de l'élève injectées dans le prompt.

    Returns:
        Hash SHA256 (16 premiers caractères).
    """
    template = get_prompt(template_name)

    # Construire le prompt complet
    full_prompt = json.dumps(
        {
            "template": template_name or CURRENT_PROMPT,
            "version": template["version"],
            "system": template["system"],
            "user": template["user"].format(eleve_data=eleve_data),
        },
        ensure_ascii=False,
        sort_keys=True,
    )

    return hashlib.sha256(full_prompt.encode()).hexdigest()[:16]


def list_prompts() -> list[dict]:
    """Liste tous les templates disponibles.

    Returns:
        Liste de dicts avec name, version, description.
    """
    return [
        {
            "name": name,
            "version": data["version"],
            "description": data.get("description", ""),
            "is_current": name == CURRENT_PROMPT,
        }
        for name, data in PROMPT_TEMPLATES.items()
    ]
