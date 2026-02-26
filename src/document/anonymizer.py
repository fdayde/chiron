"""Extraction du nom d'élève depuis le PDF.

Fonction principale :
- extract_eleve_name() : extrait le nom de l'élève depuis le PDF (regex).

La pseudonymisation des textes est assurée par ``pseudonymization.py``
(pipeline 3 passes : regex + Flair NER fuzzy + fuzzy direct).
"""

import re
from pathlib import Path

import pdfplumber


def extract_eleve_name(pdf_path: str | Path) -> dict | None:
    """Extrait le nom de l'élève depuis le PDF.

    Deux stratégies chaînées :
    1. "Élève : NOM Prénom" (bulletins de test)
    2. "NOM Prénom\\nNé(e) le" (PRONOTE réel)

    Args:
        pdf_path: Chemin vers le fichier PDF.

    Returns:
        Dict avec 'nom', 'prenom', 'nom_complet', 'texte_complet', ou None si non trouvé.
    """
    pdf_path = Path(pdf_path)

    with pdfplumber.open(pdf_path) as pdf:
        text_complet = ""
        for page in pdf.pages:
            text_complet += (page.extract_text() or "") + "\n"

        # Stratégie 1 : "Élève : NOM Prénom" (bulletins de test)
        match = re.search(r"[ÉE]l[èe]ve\s*:\s*([^\n]+)", text_complet, re.IGNORECASE)

        # Stratégie 2 : "NOM Prénom" avant "Né(e) le" (PRONOTE réel)
        # Le prénom (casse mixte) discrimine vs ville/CP (tout majuscules).
        # Le regex échoue sur les mots tout-MAJUSCULES comme "BOUILLARGUES"
        # car [a-zà-ü]+ exige des minuscules après la première lettre.
        if not match:
            match = re.search(
                r"([A-ZÀ-Ü][-A-ZÀ-Ü]+\s+[A-Za-zÀ-ü][a-zà-ü]+(?:-[A-Za-zÀ-ü][a-zà-ü]+)*)\s*\n\s*Né[e]?\s+le",
                text_complet,
            )

        if not match:
            return None

        nom_complet = match.group(1).strip()
        parts = nom_complet.split()

        # Déterminer nom/prénom selon le format détecté
        # Stratégie 1 : "Marie Dupont" → prenom=Marie, nom=Dupont
        # Stratégie 2 : "AMET Lenny" → nom=AMET (majuscules), prenom=Lenny
        if parts and all(c.isupper() or not c.isalpha() for c in parts[0]):
            # Premier mot tout en majuscules → format PRONOTE : NOM Prénom
            nom_parts = []
            prenom_parts = []
            for part in parts:
                if all(c.isupper() or not c.isalpha() for c in part):
                    nom_parts.append(part)
                else:
                    prenom_parts.append(part)
            nom = " ".join(nom_parts) if nom_parts else parts[0]
            prenom = " ".join(prenom_parts) if prenom_parts else None
        else:
            # Format test : Prénom Nom
            prenom = parts[0] if parts else None
            nom = " ".join(parts[1:]) if len(parts) > 1 else parts[0] if parts else None

        return {
            "nom": nom,
            "prenom": prenom,
            "nom_complet": nom_complet,
            "texte_complet": text_complet,
        }
