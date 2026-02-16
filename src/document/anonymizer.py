"""Extraction du nom d'élève et détection NER de noms.

Fonctions principales :
- extract_eleve_name() : extrait le nom de l'élève depuis le PDF (regex).
- ner_check_student_names() : filet de sécurité NER sur des textes courts
  (appréciations) après pseudonymisation regex.
"""

import logging
import re
import threading
from pathlib import Path

import pdfplumber

from src.llm.config import settings as llm_settings

logger = logging.getLogger(__name__)

# Labels NER pour les personnes (compatibles avec différents modèles)
PERSON_LABELS = {"PER", "PERSON", "I-PER", "B-PER"}

# Pipeline NER (lazy loading, thread-safe)
_ner_pipeline = None
_ner_lock = threading.Lock()


def _get_ner_pipeline():
    """Charge le pipeline NER (lazy loading, thread-safe)."""
    global _ner_pipeline
    if _ner_pipeline is None:
        with _ner_lock:
            if _ner_pipeline is None:  # Double-check après acquisition du lock
                from transformers import pipeline

                logger.info(f"Chargement du modèle NER: {llm_settings.ner_model}")
                _ner_pipeline = pipeline(
                    "ner",
                    model=llm_settings.ner_model,
                    aggregation_strategy="simple",
                )
    return _ner_pipeline


def extract_eleve_name(pdf_path: str | Path) -> dict | None:
    """Extrait le nom de l'élève depuis le PDF.

    Deux stratégies chaînées :
    1. "Élève : NOM Prénom" (bulletins de test)
    2. "NOM Prénom\\nNé(e) le" (PRONOTE réel)

    Args:
        pdf_path: Chemin vers le fichier PDF.

    Returns:
        Dict avec 'nom', 'prenom', 'nom_complet', 'genre', ou None si non trouvé.
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

        # Extraire le genre si présent
        genre = None
        genre_match = re.search(
            r"Genre\s*:\s*(Fille|Garçon)", text_complet, re.IGNORECASE
        )
        if genre_match:
            genre = "Fille" if "fille" in genre_match.group(1).lower() else "Garçon"

        return {
            "nom": nom,
            "prenom": prenom,
            "nom_complet": nom_complet,
            "genre": genre,
            "texte_complet": text_complet,
        }


def ner_check_student_names(
    texts: list[str],
    nom_parts: set[str],
) -> list[str]:
    """Détecte les variantes du nom de l'élève dans des textes courts via NER.

    Filet de sécurité après la pseudonymisation regex.
    Retourne les variantes trouvées (à remplacer par eleve_id).
    """
    nlp = _get_ner_pipeline()
    found: set[str] = set()
    for text in texts:
        if not text:
            continue
        entities = nlp(text)
        for e in entities:
            if e.get("entity_group", "").upper() not in PERSON_LABELS:
                continue
            word = e["word"].strip()
            word_parts = {p.lower() for p in word.split() if len(p) > 1}
            if word_parts & nom_parts:
                found.add(word)
    return sorted(found, key=len, reverse=True)
