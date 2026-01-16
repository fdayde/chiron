"""Parser spécifique pour les bulletins scolaires PRONOTE."""

import logging
from pathlib import Path

from src.core.models import EleveExtraction, MatiereExtraction
from src.document.parser import extract_pdf_content, parse_float
from src.document.patterns import (
    detect_genre,
    extract_all_matches,
    extract_field,
    extract_nom_prenom,
    extract_notes,
)


def _clean_cell(text: str | None) -> str:
    """Clean cell text while preserving newlines.

    Unlike clean_text(), this preserves line breaks for multi-line cell parsing.

    Args:
        text: Raw cell text.

    Returns:
        Cleaned text with newlines preserved.
    """
    if not text:
        return ""

    # Normalize each line separately
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        # Normalize multiple spaces to single space
        line = " ".join(line.split())
        if line:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


logger = logging.getLogger(__name__)

# Mots-clés pour ignorer les lignes non-matière dans les tableaux
SKIP_ROW_KEYWORDS = frozenset(
    [
        "matière",
        "discipline",
        "moyenne",
        "total",
        "élève",
        "classe",
        "appréciation",
        "note",
        "coefficient",
    ]
)


class BulletinParser:
    """Parser pour bulletins scolaires au format PDF PRONOTE.

    Le format attendu est un tableau à 4 colonnes :
    - Matières (+ nom du professeur)
    - Moyennes (élève | classe + écrit/oral si applicable)
    - Éléments du programme (compétences)
    - Appréciations

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

        Uses centralized patterns from patterns.py for extraction.

        Args:
            text: Texte brut du bulletin.

        Returns:
            Dict avec nom, prenom, classe, trimestre, absences, etc.
        """
        info: dict = {
            "nom": None,
            "prenom": None,
            "genre": None,
            "classe": None,
            "trimestre": None,
            "absences_demi_journees": None,
            "absences_justifiees": None,
            "retards": None,
            "engagements": [],
        }

        # Extract nom and prénom
        nom, prenom = extract_nom_prenom(text)
        info["nom"] = nom
        info["prenom"] = prenom

        # Extract classe
        classe = extract_field("classe", text)
        if classe:
            info["classe"] = classe.strip()

        # Extract trimestre
        trimestre_str = extract_field("trimestre", text)
        if trimestre_str:
            try:
                info["trimestre"] = int(trimestre_str)
            except ValueError:
                logger.warning(f"Could not parse trimestre: {trimestre_str}")

        # Extract absences
        absences_str = extract_field("absences", text)
        if absences_str:
            try:
                info["absences_demi_journees"] = int(absences_str)
            except ValueError:
                logger.warning(f"Could not parse absences: {absences_str}")

        # Check if absences are justified
        justif_match = extract_field("absences_justifiees", text)
        if justif_match:
            # "non justifiées" -> False, "justifiées" -> True
            info["absences_justifiees"] = "non" not in justif_match.lower()

        # Extract retards
        retards_str = extract_field("retards", text)
        if retards_str:
            try:
                info["retards"] = int(retards_str)
            except ValueError:
                logger.warning(f"Could not parse retards: {retards_str}")

        # Extract engagements
        engagements = extract_all_matches("engagement", text)
        if engagements:
            info["engagements"] = engagements

        # Detect genre from text (if not explicitly stated)
        # Look in the entire text for grammatical markers
        detected_genre = detect_genre(text)
        if detected_genre:
            info["genre"] = detected_genre

        return info

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

        Supporte deux formats :
        - 4 colonnes (PRONOTE complet) : Matière | Moyennes | Compétences | Appréciation
        - 3 colonnes (simplifié) : Matière | Moyennes | Appréciation

        Args:
            row: Ligne du tableau.

        Returns:
            MatiereExtraction ou None si ligne invalide.
        """
        if not row or len(row) < 2:
            return None

        # Détecter le format (3 ou 4 colonnes)
        num_cols = len(row)

        # Column 0: Matière + professeur
        matiere_cell = _clean_cell(row[0])
        if not matiere_cell:
            return None

        # Split matière and professeur
        # Professor line starts with "M." or "Mme" or "M "
        matiere_lines = matiere_cell.split("\n")
        nom_parts = []
        professeur = None

        for line in matiere_lines:
            line = line.strip()
            # Detect professor line
            if line.startswith(("M.", "Mme ", "M ")) or line.startswith("Mme."):
                professeur = line
            else:
                nom_parts.append(line)

        # Join nom parts, handling word breaks
        # Heuristic: if previous part contains a hyphen but doesn't end with hyphen,
        # it's likely a broken hyphenated word (e.g., "HISTOIRE-GEOGRAP" + "HIE-EMC")
        nom = ""
        for i, part in enumerate(nom_parts):
            if i == 0:
                nom = part
            elif nom and "-" in nom and not nom.endswith("-"):
                # Previous part has a hyphen but doesn't end with it
                # This is likely a broken compound word, join without space
                nom += part
            else:
                nom += " " + part

        # Skip headers ou lignes non-matière
        nom_lower = nom.lower()
        if any(kw in nom_lower for kw in SKIP_ROW_KEYWORDS):
            return None

        # Column 1: Moyennes (format: "12.50 | 10.83\nÉcrit 15.00 | 11.25\nOral 13.00 | 10.40")
        note_cell = _clean_cell(row[1]) if row[1] else ""

        # Extract main moyenne from first line
        note_lines = note_cell.split("\n")
        moyenne_eleve, moyenne_classe = None, None
        if note_lines:
            moyenne_eleve, moyenne_classe = extract_notes(note_lines[0])

        # Fallback to simple float parsing if pattern didn't match
        if moyenne_eleve is None and note_lines:
            moyenne_eleve = parse_float(note_lines[0])

        # Extract écrit/oral notes from subsequent lines
        note_ecrit, moyenne_ecrit_classe = None, None
        note_oral, moyenne_oral_classe = None, None

        for line in note_lines[1:]:  # Skip first line (main moyenne)
            line_lower = line.lower()
            if "écrit" in line_lower or "ecrit" in line_lower:
                # Extract écrit notes
                ecrit_nums = self._extract_note_pair(line)
                if ecrit_nums:
                    note_ecrit = ecrit_nums[0]
                    moyenne_ecrit_classe = (
                        ecrit_nums[1] if len(ecrit_nums) > 1 else None
                    )
            elif "oral" in line_lower:
                # Extract oral notes
                oral_nums = self._extract_note_pair(line)
                if oral_nums:
                    note_oral = oral_nums[0]
                    moyenne_oral_classe = oral_nums[1] if len(oral_nums) > 1 else None

        # Colonnes 2 et 3 : dépend du format
        competences: list[str] = []
        appreciation = ""

        if num_cols == 3:
            # Format simplifié : [Matière, Notes, Appréciation]
            if row[2]:
                appreciation = " ".join(_clean_cell(row[2]).split("\n"))
        else:
            # Format PRONOTE complet : [Matière, Notes, Compétences, Appréciation]
            # Column 2: Compétences (format: "- comp1\n- comp2")
            if len(row) > 2 and row[2]:
                comp_cell = _clean_cell(row[2])
                if comp_cell:
                    current_comp = ""
                    for line in comp_cell.split("\n"):
                        line = line.strip()
                        if line.startswith("-"):
                            # Save previous competence if exists
                            if current_comp:
                                competences.append(current_comp)
                            # Start new competence
                            current_comp = line[1:].strip()
                        elif current_comp:
                            # Continuation of previous line
                            current_comp += " " + line
                        elif line:
                            # No bullet point, treat as single competence
                            current_comp = line
                    # Don't forget last competence
                    if current_comp:
                        competences.append(current_comp)

            # Column 3: Appréciation (join lines with space)
            if len(row) > 3 and row[3]:
                appreciation = " ".join(_clean_cell(row[3]).split("\n"))

        return MatiereExtraction(
            nom=nom,
            professeur=professeur,
            moyenne_eleve=moyenne_eleve,
            moyenne_classe=moyenne_classe,
            note_ecrit=note_ecrit,
            note_oral=note_oral,
            moyenne_ecrit_classe=moyenne_ecrit_classe,
            moyenne_oral_classe=moyenne_oral_classe,
            competences=competences,
            appreciation=appreciation,
        )

    def _extract_note_pair(self, text: str) -> list[float] | None:
        """Extract a pair of notes from text like 'Écrit 15.00 | 11.25'.

        Args:
            text: Text containing notes.

        Returns:
            List of float values found, or None if none found.
        """
        import re

        # Find all numbers in the text
        nums = re.findall(r"(\d+[.,]?\d*)", text)
        if not nums:
            return None

        result = []
        for n in nums:
            try:
                result.append(float(n.replace(",", ".")))
            except ValueError:
                continue

        return result if result else None
