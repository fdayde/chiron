"""Anonymisation de PDFs avant parsing ou envoi cloud.

Ce module extrait le nom de l'élève et anonymise le PDF en remplaçant
toutes les occurrences du nom par un identifiant anonyme.

Usage:
    from src.document.anonymizer import extract_eleve_name, anonymize_pdf

    # 1. Extraire le nom
    identity = extract_eleve_name(pdf_path)
    # identity = {"nom": "Dupont", "prenom": "Marie", "nom_complet": "Marie Dupont"}

    # 2. Anonymiser le PDF
    pdf_bytes = anonymize_pdf(pdf_path, "ELEVE_001")
"""

import logging
import re
import threading
from pathlib import Path

import fitz  # PyMuPDF
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

    Recherche le pattern "Élève : <nom>" et parse en nom/prénom.

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

        # Pattern: "Élève : NOM" ou "Elève : NOM" (case insensitive)
        match = re.search(r"[ÉE]l[èe]ve\s*:\s*([^\n]+)", text_complet, re.IGNORECASE)
        if not match:
            return None

        nom_complet = match.group(1).strip()

        # Parser nom/prénom (heuristique: premier mot = prénom)
        parts = nom_complet.split()
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


def anonymize_pdf(pdf_path: str | Path, eleve_id: str) -> bytes:
    """Anonymise un PDF en remplaçant le nom de l'élève par eleve_id.

    Args:
        pdf_path: Chemin vers le PDF original.
        eleve_id: Identifiant anonyme (ex: "ELEVE_001").

    Returns:
        Bytes du PDF anonymisé.

    Raises:
        ValueError: Si le nom de l'élève n'a pas pu être extrait.
    """
    pdf_path = Path(pdf_path)

    # 1. Extraire le nom
    identity = extract_eleve_name(pdf_path)
    if not identity:
        raise ValueError(f"Impossible d'extraire le nom de l'élève depuis {pdf_path}")

    nom_complet = identity["nom_complet"]
    texte_complet = identity["texte_complet"]
    logger.info(f"Nom extrait: '{nom_complet}'")

    # 2. Détecter les variantes avec NER
    variants = _detect_name_variants(texte_complet, nom_complet)
    logger.info(f"Variantes détectées: {variants}")

    # 3. Anonymiser le PDF
    pdf_bytes, count = _replace_names_in_pdf(pdf_path, variants, eleve_id)
    logger.info(f"Anonymisation terminée: {count} remplacements")

    return pdf_bytes


def _detect_name_variants(text: str, nom_entete: str) -> list[str]:
    """Détecte toutes les variantes du nom dans le texte avec NER.

    Args:
        text: Texte complet du PDF.
        nom_entete: Nom extrait de l'en-tête "Élève : XXX".

    Returns:
        Liste des variantes à anonymiser, triées par longueur (desc).
    """
    nlp = _get_ner_pipeline()

    # Découper en chunks pour respecter la limite de tokens
    chunks = _split_into_chunks(text, max_chars=2000)

    # Extraire les entités PER
    personnes = []
    for chunk in chunks:
        try:
            entities = nlp(chunk)
            personnes.extend(
                e["word"]
                for e in entities
                if e.get("entity_group", "").upper() in PERSON_LABELS
                or "PER" in e.get("entity_group", "").upper()
            )
        except Exception as e:
            logger.warning(f"Erreur NER sur chunk: {e}")

    # Filtrer pour garder uniquement les variantes du nom de l'élève
    variants = set()
    nom_entete_clean = nom_entete.strip()
    nom_parts = [p.lower() for p in nom_entete_clean.split()]

    for personne in set(personnes):
        personne_clean = personne.strip()
        if not personne_clean:
            continue
        personne_parts = personne_clean.lower().split()
        # Match si au moins une partie correspond
        if any(part in nom_parts for part in personne_parts):
            variants.add(personne_clean)

    # Toujours inclure le nom complet de l'en-tête
    variants.add(nom_entete_clean)

    # Trier par longueur décroissante (remplacer les plus longs d'abord)
    return sorted(variants, key=len, reverse=True)


def _replace_names_in_pdf(
    pdf_path: Path,
    noms_a_remplacer: list[str],
    nom_anonyme: str,
) -> tuple[bytes, int]:
    """Remplace les noms dans le PDF et retourne les bytes.

    Args:
        pdf_path: Chemin vers le PDF original.
        noms_a_remplacer: Liste des variantes à remplacer.
        nom_anonyme: Nom de remplacement (ex: "ELEVE_001").

    Returns:
        Tuple (bytes du PDF anonymisé, nombre de remplacements).
    """
    # Optimisation PyMuPDF pour éviter de supprimer du texte adjacent
    fitz.TOOLS.set_small_glyph_heights(True)

    with fitz.open(pdf_path) as doc:
        total_replacements = 0

        for page in doc:
            for nom in noms_a_remplacer:
                instances = page.search_for(nom)

                for rect in instances:
                    # fontname="helv" force Helvetica (police base-14) pour
                    # éviter le dédoublement de caractères lié aux polices
                    # TrueType/CID du PDF source
                    page.add_redact_annot(
                        rect,
                        text=nom_anonyme,
                        fontname="helv",
                        fontsize=10,
                        fill=(1, 1, 1),
                    )
                    total_replacements += 1

            page.apply_redactions()

        return doc.tobytes(), total_replacements


def _split_into_chunks(text: str, max_chars: int = 2000) -> list[str]:
    """Découpe le texte en chunks en respectant les fins de phrases."""
    sentences = re.split(r"(?<=[.!?])\s+", text)

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) < max_chars:
            current_chunk += sentence + " "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + " "

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text]
