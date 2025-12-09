"""Parser spécifique pour les bulletins scolaires PRONOTE."""

import logging
from pathlib import Path

from src.core.models import EleveExtraction, MatiereExtraction
from src.document.parser import clean_text, extract_pdf_content, parse_float

logger = logging.getLogger(__name__)

# Mots-clés pour ignorer les lignes non-matière dans les tableaux
SKIP_ROW_KEYWORDS = frozenset(["matière", "discipline", "moyenne", "total"])


class BulletinParser:
    """Parser pour bulletins scolaires au format PDF PRONOTE.

    Le format attendu est un tableau à 3 colonnes :
    - Matière
    - Note élève (+ moyenne classe)
    - Appréciation

    Usage:
        parser = BulletinParser()
        eleves = parser.parse("bulletin_3A_T1.pdf")
    """

    def parse(self, pdf_path: str | Path) -> list[EleveExtraction]:
        """Parse un PDF bulletin et extrait les données élèves.

        Args:
            pdf_path: Chemin vers le fichier PDF.

        Returns:
            Liste d'EleveExtraction (un ou plusieurs si multi-élèves).
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF non trouvé: {pdf_path}")

        logger.info(f"Parsing bulletin: {pdf_path.name}")

        # Extraire contenu PDF en une seule passe
        content = extract_pdf_content(pdf_path)

        # Parser les données
        eleves = self._parse_content(content.tables, content.text)

        logger.info(f"Extrait {len(eleves)} élève(s) de {pdf_path.name}")
        return eleves

    def _parse_content(
        self, tables: list[list[list[str | None]]], text: str
    ) -> list[EleveExtraction]:
        """Parse le contenu extrait.

        Args:
            tables: Tableaux extraits du PDF.
            text: Texte brut extrait.

        Returns:
            Liste d'élèves extraits.
        """
        # TODO: Implémenter selon structure réelle du PDF PRONOTE
        # Pour l'instant, structure de base

        eleves: list[EleveExtraction] = []

        # Extraire infos élève depuis texte (header bulletin)
        eleve_info = self._extract_eleve_info(text)

        # Extraire matières depuis tableaux
        matieres = self._extract_matieres(tables)

        if matieres:
            eleve = EleveExtraction(
                **eleve_info,
                matieres=matieres,
            )
            eleves.append(eleve)

        return eleves

    def _extract_eleve_info(self, text: str) -> dict:
        """Extrait les informations de l'élève depuis le texte.

        Args:
            text: Texte brut du bulletin.

        Returns:
            Dict avec nom, prenom, classe, trimestre, absences, etc.
        """
        # TODO: Implémenter regex selon format réel
        # Patterns typiques PRONOTE :
        # - "NOM Prénom"
        # - "Classe : 3ème A"
        # - "Trimestre 1"
        # - "Absences : 4 demi-journées"

        return {
            "nom": None,
            "prenom": None,
            "classe": None,
            "trimestre": None,
            "absences_demi_journees": None,
            "absences_justifiees": None,
            "retards": None,
        }

    def _extract_matieres(
        self, tables: list[list[list[str | None]]]
    ) -> list[MatiereExtraction]:
        """Extrait les matières depuis les tableaux.

        Args:
            tables: Tableaux extraits du PDF.

        Returns:
            Liste de MatiereExtraction.
        """
        matieres: list[MatiereExtraction] = []

        for table in tables:
            for row in table:
                matiere = self._parse_matiere_row(row)
                if matiere:
                    matieres.append(matiere)

        return matieres

    def _parse_matiere_row(self, row: list[str | None]) -> MatiereExtraction | None:
        """Parse une ligne de tableau comme matière.

        Format attendu (3 colonnes) :
        - [0] Matière
        - [1] Note élève / Moyenne classe
        - [2] Appréciation

        Args:
            row: Ligne du tableau.

        Returns:
            MatiereExtraction ou None si ligne invalide.
        """
        if not row or len(row) < 3:
            return None

        nom = clean_text(row[0])
        if not nom:
            return None

        # Skip headers ou lignes non-matière
        if any(kw in nom.lower() for kw in SKIP_ROW_KEYWORDS):
            return None

        # Parser notes
        note_cell = clean_text(row[1])
        moyenne_eleve = parse_float(note_cell)

        # TODO: Extraire moyenne classe si présente dans la même cellule
        moyenne_classe = None

        # Appréciation
        appreciation = clean_text(row[2]) if len(row) > 2 else ""

        return MatiereExtraction(
            nom=nom,
            moyenne_eleve=moyenne_eleve,
            moyenne_classe=moyenne_classe,
            appreciation=appreciation,
        )
