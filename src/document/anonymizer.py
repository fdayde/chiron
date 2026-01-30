"""Anonymisation de PDFs avant envoi cloud.

Ce module remplace les noms d'élèves dans les PDFs avant envoi à l'OCR cloud,
garantissant que les données personnelles ne quittent jamais la machine locale.

Flow:
    PDF original → extract_eleve_name() → detect_name_variants() → anonymize_pdf() → PDF anonymisé

Usage:
    from src.document.anonymizer import PDFAnonymizer

    anonymizer = PDFAnonymizer()
    result = anonymizer.anonymize(pdf_path, eleve_id="ELEVE_001")
    # result.pdf_bytes: PDF anonymisé
    # result.identity: {"nom": "Dupont", "prenom": "Marie", ...}
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF
import pdfplumber

from src.llm.config import settings as llm_settings

logger = logging.getLogger(__name__)

# Labels NER pour les personnes (compatibles avec différents modèles)
PERSON_LABELS = {"PER", "PERSON", "I-PER", "B-PER"}


@dataclass
class AnonymizationResult:
    """Résultat de l'anonymisation d'un PDF."""

    pdf_bytes: bytes
    """PDF anonymisé en bytes."""

    eleve_id: str
    """Identifiant anonyme (ex: ELEVE_001)."""

    identity: dict
    """Identité originale extraite (nom, prenom, etc.)."""

    replacements_count: int
    """Nombre de remplacements effectués."""

    variants_found: list[str]
    """Variantes du nom détectées."""


class PDFAnonymizer:
    """Anonymise les PDFs en remplaçant les noms d'élèves.

    Utilise CamemBERT NER pour détecter toutes les mentions du nom,
    puis PyMuPDF pour les remplacer visuellement dans le PDF.
    """

    def __init__(self, ner_model: str | None = None):
        """Initialise l'anonymizer.

        Args:
            ner_model: Modèle HuggingFace NER à utiliser.
                Par défaut: config ner_model (CamemBERT v1).
        """
        self._ner_model_name = ner_model or llm_settings.ner_model
        self._ner_pipeline = None  # Lazy loading

    def _get_ner_pipeline(self):
        """Charge le pipeline NER (lazy loading pour éviter le chargement au démarrage)."""
        if self._ner_pipeline is None:
            from transformers import pipeline

            logger.info(f"Chargement du modèle NER: {self._ner_model_name}")
            self._ner_pipeline = pipeline(
                "ner",
                model=self._ner_model_name,
                aggregation_strategy="simple",
            )
        return self._ner_pipeline

    def anonymize(
        self,
        pdf_path: str | Path,
        eleve_id: str,
    ) -> AnonymizationResult:
        """Anonymise un PDF en remplaçant le nom de l'élève.

        Args:
            pdf_path: Chemin vers le PDF original.
            eleve_id: Identifiant anonyme à utiliser (ex: "ELEVE_001").

        Returns:
            AnonymizationResult avec le PDF anonymisé et les métadonnées.

        Raises:
            ValueError: Si le nom de l'élève n'a pas pu être extrait.
        """
        pdf_path = Path(pdf_path)

        # 1. Extraire le nom de l'en-tête
        eleve_info = self.extract_eleve_name(pdf_path)
        if not eleve_info:
            raise ValueError(
                f"Impossible d'extraire le nom de l'élève depuis {pdf_path}"
            )

        nom_complet = eleve_info["nom_complet"]
        logger.info(f"Nom extrait de l'en-tête: '{nom_complet}'")

        # 2. Parser nom/prénom
        identity = self._parse_identity(
            nom_complet, eleve_info.get("texte_complet", "")
        )

        # 3. Détecter les variantes avec NER
        variants = self.detect_name_variants(
            eleve_info["texte_complet"],
            nom_complet,
        )
        logger.info(f"Variantes détectées: {variants}")

        # 4. Anonymiser le PDF
        pdf_bytes, count = self._anonymize_pdf(pdf_path, variants, eleve_id)
        logger.info(f"Anonymisation terminée: {count} remplacements")

        return AnonymizationResult(
            pdf_bytes=pdf_bytes,
            eleve_id=eleve_id,
            identity=identity,
            replacements_count=count,
            variants_found=variants,
        )

    def extract_eleve_name(self, pdf_path: Path) -> dict | None:
        """Extrait le nom de l'élève depuis le PDF.

        Recherche le pattern "Élève : <nom>" et capture le texte.

        Args:
            pdf_path: Chemin vers le fichier PDF.

        Returns:
            Dict avec 'nom_complet' et 'texte_complet', ou None si non trouvé.
        """
        with pdfplumber.open(pdf_path) as pdf:
            text_complet = ""
            for page in pdf.pages:
                text_complet += (page.extract_text() or "") + "\n"

            # Pattern: "Élève : NOM" ou "Elève : NOM" (case insensitive)
            match = re.search(
                r"[ÉE]l[èe]ve\s*:\s*([^\n]+)", text_complet, re.IGNORECASE
            )
            if match:
                return {
                    "nom_complet": match.group(1).strip(),
                    "texte_complet": text_complet,
                }
        return None

    def detect_name_variants(
        self,
        text: str,
        nom_entete: str,
    ) -> list[str]:
        """Détecte toutes les variantes du nom dans le texte avec NER.

        Args:
            text: Texte complet du PDF.
            nom_entete: Nom extrait de l'en-tête "Élève : XXX".

        Returns:
            Liste des variantes à anonymiser, triées par longueur (desc).
        """
        nlp = self._get_ner_pipeline()

        # Découper en chunks pour respecter la limite de tokens
        chunks = self._split_into_chunks(text, max_chars=2000)

        # Extraire les entités PER
        personnes = []
        for chunk in chunks:
            try:
                entities = nlp(chunk)
                personnes.extend(
                    [
                        e["word"]
                        for e in entities
                        if self._is_person_entity(e.get("entity_group", ""))
                    ]
                )
            except Exception as e:
                logger.warning(f"Erreur NER sur chunk: {e}")

        # Filtrer pour garder uniquement les variantes du nom de l'élève
        return self._find_eleve_variants(nom_entete, personnes)

    def _parse_identity(self, nom_complet: str, texte: str) -> dict:
        """Parse le nom complet en prénom/nom et extrait d'autres infos.

        Args:
            nom_complet: Nom complet extrait ("Marie Dupont").
            texte: Texte complet du PDF pour extraire d'autres infos.

        Returns:
            Dict avec nom, prenom, genre, etablissement, classe.
        """
        parts = nom_complet.strip().split()

        # Heuristique simple: premier mot = prénom, reste = nom
        prenom = parts[0] if parts else None
        nom = " ".join(parts[1:]) if len(parts) > 1 else None

        # Extraire le genre si présent (format Fille/Garçon pour cohérence avec models.py)
        genre = None
        genre_match = re.search(r"Genre\s*:\s*(Fille|Garçon)", texte, re.IGNORECASE)
        if genre_match:
            genre = "Fille" if "fille" in genre_match.group(1).lower() else "Garçon"

        # Extraire l'établissement (première ligne souvent)
        etablissement = None
        lines = texte.strip().split("\n")
        if lines and not re.match(r"bulletin|élève", lines[0], re.IGNORECASE):
            etablissement = lines[0].strip()

        return {
            "nom_original": nom,
            "prenom_original": prenom,
            "nom_complet": nom_complet,
            "genre": genre,
            "etablissement": etablissement,
        }

    def _anonymize_pdf(
        self,
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

        doc = fitz.open(pdf_path)
        total_replacements = 0

        for page in doc:
            for nom in noms_a_remplacer:
                instances = page.search_for(nom)

                for rect in instances:
                    page.add_redact_annot(
                        rect,
                        text=nom_anonyme,
                        fill=(1, 1, 1),  # Fond blanc
                        fontsize=10,
                    )
                    total_replacements += 1

            page.apply_redactions()

        return doc.tobytes(), total_replacements

    def _split_into_chunks(self, text: str, max_chars: int = 2000) -> list[str]:
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

    def _is_person_entity(self, entity_group: str) -> bool:
        """Vérifie si le label correspond à une personne."""
        return entity_group.upper() in PERSON_LABELS or "PER" in entity_group.upper()

    def _find_eleve_variants(
        self,
        nom_entete: str,
        personnes_ner: list[str],
    ) -> list[str]:
        """Compare le nom de l'en-tête avec les entités NER.

        Args:
            nom_entete: Nom extrait de "Élève : XXX".
            personnes_ner: Liste des personnes détectées par NER.

        Returns:
            Liste des variantes à anonymiser (triées par longueur desc).
        """
        variants = set()

        nom_entete_clean = nom_entete.strip()
        nom_parts = [p.lower() for p in nom_entete_clean.split()]

        for personne in set(personnes_ner):
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


# Singleton pour éviter de recharger le modèle NER
_anonymizer_instance: PDFAnonymizer | None = None


def get_anonymizer() -> PDFAnonymizer:
    """Retourne l'instance singleton de l'anonymizer."""
    global _anonymizer_instance
    if _anonymizer_instance is None:
        _anonymizer_instance = PDFAnonymizer()
    return _anonymizer_instance
