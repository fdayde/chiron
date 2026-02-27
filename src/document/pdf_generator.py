"""Générateur de bulletins PDF synthétiques.

Génère des bulletins PDF à partir de données EleveExtraction/EleveGroundTruth,
imitant le format PRONOTE pour tester le parser.

Structure PRONOTE :
- Header avec infos établissement
- Tableau 4 colonnes : Matières | Moyennes | Éléments du programme | Appréciations
- Footer avec engagements, parcours, absences
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from reportlab.lib.colors import Color
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src.core.constants import DATA_DIR
from src.document.templates import (
    COLORS,
    FONTS,
    LABELS,
    MARGINS,
    PAGE_SIZE,
    TABLE_COLUMN_WIDTHS,
    TABLE_CONFIG,
)

if TYPE_CHECKING:
    from src.core.models import EleveExtraction, EleveGroundTruth

logger = logging.getLogger(__name__)


def _color_from_tuple(rgb: tuple[float, float, float]) -> Color:
    """Convertit un tuple RGB (échelle 0-1) en Color reportlab."""
    return Color(rgb[0], rgb[1], rgb[2])


def _escape_html(text: str) -> str:
    """Échappe les caractères spéciaux HTML pour Paragraph."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class BulletinPDFGenerator:
    """Génère des bulletins PDF synthétiques à partir de données élèves.

    Crée des PDF imitant le format PRONOTE :
    - En-tête avec infos établissement et élève
    - Tableau 4 colonnes (Matières, Moyennes, Éléments programme, Appréciations)
    - Pied de page avec engagements, parcours, absences

    Usage:
        generator = BulletinPDFGenerator()
        pdf_path = generator.generate(eleve, etablissement="Collège Test")
    """

    def __init__(
        self,
        output_dir: Path | None = None,
    ) -> None:
        """Initialise le générateur.

        Args:
            output_dir: Répertoire de sortie (défaut: data/raw).
        """
        self.output_dir = Path(output_dir) if output_dir else DATA_DIR / "raw"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._init_styles()

    def _init_styles(self) -> None:
        """Initialise les styles de paragraphe."""
        self.styles = getSampleStyleSheet()

        # Header title style (centered)
        self.styles.add(
            ParagraphStyle(
                name="BulletinTitle",
                fontName=FONTS["family_bold"],
                fontSize=FONTS["sizes"]["title"],
                alignment=1,  # Center
                spaceAfter=2,
            )
        )

        # Subtitle (no duplicate notice)
        self.styles.add(
            ParagraphStyle(
                name="Subtitle",
                fontName=FONTS["family"],
                fontSize=FONTS["sizes"]["small"],
                alignment=1,  # Center
                spaceAfter=6,
                textColor=_color_from_tuple(COLORS["text_light"]),
            )
        )

        # Table cell style
        self.styles.add(
            ParagraphStyle(
                name="TableCell",
                fontName=FONTS["family"],
                fontSize=TABLE_CONFIG["font_size_body"],
                leading=TABLE_CONFIG["font_size_body"] + 2,
            )
        )

        # Table cell small (for professor name, sub-notes)
        self.styles.add(
            ParagraphStyle(
                name="TableCellSmall",
                fontName=FONTS["family"],
                fontSize=TABLE_CONFIG["font_size_prof"],
                leading=TABLE_CONFIG["font_size_prof"] + 2,
                textColor=_color_from_tuple(COLORS["text_light"]),
            )
        )

        # Footer style
        self.styles.add(
            ParagraphStyle(
                name="Footer",
                fontName=FONTS["family"],
                fontSize=FONTS["sizes"]["small"],
                leading=FONTS["sizes"]["small"] + 3,
            )
        )

        # Signature style (right aligned)
        self.styles.add(
            ParagraphStyle(
                name="Signature",
                fontName=FONTS["family"],
                fontSize=FONTS["sizes"]["small"],
                alignment=2,  # Right
            )
        )

    def generate(
        self,
        eleve: "EleveExtraction | EleveGroundTruth",
        etablissement: str = "Collège Test",
        filename: str | None = None,
    ) -> Path:
        """Génère un bulletin PDF unique.

        Args:
            eleve: Données de l'élève.
            etablissement: Nom de l'établissement pour l'en-tête.
            filename: Nom de fichier personnalisé (défaut: {eleve_id}.pdf).

        Returns:
            Chemin vers le PDF généré.
        """
        # Determine filename
        if filename is None:
            eleve_id = eleve.eleve_id or eleve.nom or "eleve"
            filename = f"{eleve_id}.pdf"

        output_path = self.output_dir / filename

        # Create PDF document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=PAGE_SIZE,
            leftMargin=MARGINS["left"],
            rightMargin=MARGINS["right"],
            topMargin=MARGINS["top"],
            bottomMargin=MARGINS["bottom"],
        )

        # Build content
        elements = []

        # Header section
        elements.extend(self._build_header(eleve, etablissement))

        # Spacer
        elements.append(Spacer(1, 6))

        # Grades table (4 columns)
        elements.append(self._build_table(eleve))

        # Footer with engagements, parcours, absences
        elements.extend(self._build_footer(eleve))

        # Generate PDF
        doc.build(elements)

        logger.info(f"Generated PDF: {output_path}")
        return output_path

    def generate_batch(
        self,
        eleves: list["EleveExtraction | EleveGroundTruth"],
        etablissement: str = "Collège Test",
    ) -> list[Path]:
        """Génère des PDF pour plusieurs élèves.

        Args:
            eleves: Liste d'élèves.
            etablissement: Nom de l'établissement.

        Returns:
            Liste de chemins vers les PDF générés.
        """
        paths = []
        for eleve in eleves:
            try:
                path = self.generate(eleve, etablissement)
                paths.append(path)
            except Exception as e:
                logger.error(f"Failed to generate PDF for {eleve.eleve_id}: {e}")

        logger.info(f"Generated {len(paths)}/{len(eleves)} PDFs")
        return paths

    def _build_header(
        self,
        eleve: "EleveExtraction | EleveGroundTruth",
        etablissement: str,
    ) -> list:
        """Construit l'en-tête avec infos établissement."""
        elements = []

        # No duplicate notice (small, centered, at top)
        elements.append(Paragraph(LABELS["no_duplicate"], self.styles["Subtitle"]))

        # School name
        elements.append(Paragraph(etablissement, self.styles["BulletinTitle"]))

        # Bulletin title with class and trimester
        classe_str = eleve.classe or ""
        trimestre_str = f"Trimestre {eleve.trimestre}" if eleve.trimestre else ""
        title_parts = [LABELS["bulletin_title"]]
        if classe_str:
            title_parts.append(f"- {classe_str}")
        if trimestre_str:
            title_parts.append(f"- {trimestre_str}")

        elements.append(Paragraph(" ".join(title_parts), self.styles["BulletinTitle"]))

        return elements

    def _build_table(self, eleve: "EleveExtraction | EleveGroundTruth") -> Table:
        """Construit le tableau de notes à 4 colonnes (format PRONOTE)."""
        # Header row
        header = [
            Paragraph(f"<b>{TABLE_CONFIG['columns'][0]}</b>", self.styles["TableCell"]),
            Paragraph(
                f"<b>{TABLE_CONFIG['columns'][1]}</b><br/>"
                f"<font size='7'>{LABELS['moyenne_eleve_header']} | {LABELS['moyenne_classe_header']}</font>",
                self.styles["TableCell"],
            ),
            Paragraph(
                f"<b>{TABLE_CONFIG['columns'][2]}</b><br/>"
                f"<font size='7'>{TABLE_CONFIG['sub_headers'][2]}</font>",
                self.styles["TableCell"],
            ),
            Paragraph(f"<b>{TABLE_CONFIG['columns'][3]}</b>", self.styles["TableCell"]),
        ]

        # Data rows
        data = [header]

        for matiere in eleve.matieres:
            row = self._build_matiere_row(matiere)
            data.append(row)

        # Create table
        table = Table(
            data,
            colWidths=TABLE_COLUMN_WIDTHS,
            repeatRows=1,
        )

        # Table styling
        style_commands = [
            # Header background
            ("BACKGROUND", (0, 0), (-1, 0), _color_from_tuple(COLORS["header_bg"])),
            # Borders
            ("GRID", (0, 0), (-1, -1), 0.5, _color_from_tuple(COLORS["border"])),
            # Padding
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            # Alignment
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),  # Center notes column
        ]

        # Alternating row colors
        for i in range(2, len(data), 2):
            style_commands.append(
                ("BACKGROUND", (0, i), (-1, i), _color_from_tuple(COLORS["row_alt_bg"]))
            )

        table.setStyle(TableStyle(style_commands))

        return table

    def _build_matiere_row(self, matiere) -> list:
        """Construit une ligne pour une matière."""
        # Column 1: Matière + professeur
        matiere_text = f"<b>{_escape_html(matiere.nom)}</b>"
        if matiere.professeur:
            matiere_text += (
                f"<br/><font size='7'>{_escape_html(matiere.professeur)}</font>"
            )
        matiere_cell = Paragraph(matiere_text, self.styles["TableCell"])

        # Column 2: Notes (élève / classe + écrit/oral si présent)
        note_lines = []
        if matiere.moyenne_eleve is not None:
            if matiere.moyenne_classe is not None:
                note_lines.append(
                    f"<b>{matiere.moyenne_eleve:.2f}</b> | {matiere.moyenne_classe:.2f}"
                )
            else:
                note_lines.append(f"<b>{matiere.moyenne_eleve:.2f}</b>")

        # Add écrit/oral if present
        if matiere.note_ecrit is not None:
            ecrit_str = f"{LABELS['ecrit_label']} {matiere.note_ecrit:.2f}"
            if matiere.moyenne_ecrit_classe is not None:
                ecrit_str += f" | {matiere.moyenne_ecrit_classe:.2f}"
            note_lines.append(f"<font size='7'>{ecrit_str}</font>")

        if matiere.note_oral is not None:
            oral_str = f"{LABELS['oral_label']} {matiere.note_oral:.2f}"
            if matiere.moyenne_oral_classe is not None:
                oral_str += f" | {matiere.moyenne_oral_classe:.2f}"
            note_lines.append(f"<font size='7'>{oral_str}</font>")

        note_cell = Paragraph(
            "<br/>".join(note_lines) if note_lines else "-", self.styles["TableCell"]
        )

        # Column 3: Compétences (éléments du programme)
        if matiere.competences:
            comp_text = "<br/>".join(
                f"- {_escape_html(c)}" for c in matiere.competences
            )
        else:
            comp_text = ""
        comp_cell = Paragraph(comp_text, self.styles["TableCell"])

        # Column 4: Appréciation
        appreciation = (
            _escape_html(matiere.appreciation) if matiere.appreciation else ""
        )
        appreciation_cell = Paragraph(appreciation, self.styles["TableCell"])

        return [matiere_cell, note_cell, comp_cell, appreciation_cell]

    def _build_footer(self, eleve: "EleveExtraction | EleveGroundTruth") -> list:
        """Construit le pied de page avec engagements, parcours, absences, signature."""
        elements = []
        elements.append(Spacer(1, 8))

        footer_lines = []

        # Engagements
        if eleve.engagements:
            engagements_str = ", ".join(eleve.engagements)
            footer_lines.append(
                f"<b>{LABELS['engagements_label']}</b> : {engagements_str}"
            )

        # Parcours
        if eleve.parcours:
            for parcours in eleve.parcours:
                footer_lines.append(f"<b>{parcours}</b>")

        # Événements
        if eleve.evenements:
            for evt in eleve.evenements:
                footer_lines.append(evt)

        # Absences
        if eleve.absences_demi_journees is not None:
            justif_str = (
                LABELS["justifiees"]
                if eleve.absences_justifiees
                else LABELS["non_justifiees"]
            )
            absences_str = f"<b>{LABELS['absences_label']}</b> : {eleve.absences_demi_journees} {LABELS['demi_journees']} {justif_str}"

            # Retards
            if eleve.retards:
                absences_str += f" - {eleve.retards} retard(s)"
            else:
                absences_str += f" - {LABELS['aucun_retard']}"

            footer_lines.append(absences_str)

        # Add footer content
        if footer_lines:
            elements.append(
                Paragraph("<br/>".join(footer_lines), self.styles["Footer"])
            )

        # Moyenne générale
        notes = [m.moyenne_eleve for m in eleve.matieres if m.moyenne_eleve is not None]
        if notes:
            moyenne = sum(notes) / len(notes)
            elements.append(Spacer(1, 6))
            elements.append(
                Paragraph(
                    f"<b>{LABELS['moyenne_generale_label']}</b> : {moyenne:.2f}/20",
                    self.styles["Footer"],
                )
            )

        # Signature
        elements.append(Spacer(1, 12))
        elements.append(
            Paragraph(LABELS["chef_etablissement"], self.styles["Signature"])
        )

        return elements
