"""PDF layout configuration for bulletin generation.

Centralizes all layout constants to avoid hardcoding in the generator.
Designed to mimic PRONOTE bulletin format.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

# Page dimensions
PAGE_SIZE = A4
PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE

# Margins in mm (converted to points for reportlab)
MARGINS = {
    "top": 20 * mm,
    "bottom": 15 * mm,
    "left": 15 * mm,
    "right": 15 * mm,
}

# Usable area
CONTENT_WIDTH = PAGE_WIDTH - MARGINS["left"] - MARGINS["right"]
CONTENT_HEIGHT = PAGE_HEIGHT - MARGINS["top"] - MARGINS["bottom"]

# Header section configuration
HEADER_CONFIG = {
    "height": 55 * mm,
    "etablissement_font_size": 14,
    "title_font_size": 12,
    "info_font_size": 10,
    "line_spacing": 6 * mm,
}

# Table configuration (4 colonnes comme PRONOTE)
TABLE_CONFIG = {
    "columns": ["Matières", "Moyennes", "Éléments du programme", "Appréciations"],
    "sub_headers": ["", "Élève | Classe", "travaillés durant la période", ""],
    # Column widths as proportions of content width
    "column_proportions": [0.18, 0.12, 0.35, 0.35],
    "header_height": 8 * mm,
    "row_height_min": 12 * mm,
    "row_height_per_line": 4 * mm,  # Additional height per line of text
    "max_appreciation_lines": 5,
    "font_size_header": 9,
    "font_size_body": 8,
    "font_size_prof": 7,  # Smaller font for professor name
    "padding": 2 * mm,
}

# Computed column widths
TABLE_COLUMN_WIDTHS = [CONTENT_WIDTH * p for p in TABLE_CONFIG["column_proportions"]]

# Colors (RGB tuples, 0-1 scale)
COLORS = {
    "header_bg": (0.9, 0.9, 0.9),  # Light gray for table header
    "row_alt_bg": (0.97, 0.97, 0.97),  # Very light gray for alternating rows
    "border": (0.5, 0.5, 0.5),  # Medium gray for borders
    "text": (0, 0, 0),  # Black text
    "text_light": (0.3, 0.3, 0.3),  # Dark gray for secondary text
}

# Font configuration
FONTS = {
    "family": "Helvetica",
    "family_bold": "Helvetica-Bold",
    "sizes": {
        "title": 14,
        "header": 12,
        "body": 10,
        "small": 9,
        "table_header": 10,
        "table_body": 9,
    },
}

# Text labels (French)
LABELS = {
    "bulletin_title": "BULLETIN SCOLAIRE",
    "no_duplicate": "Aucun duplicata ne sera délivré",
    "etablissement_default": "Établissement",
    "classe_label": "Classe",
    "trimestre_label": "Trimestre",
    "eleve_label": "Élève",
    "absences_label": "Absences",
    "retards_label": "Retards",
    "aucun_retard": "Aucun retard",
    "engagements_label": "Engagements",
    "parcours_label": "Parcours",
    "demi_journees": "demi-journées",
    "justifiees": "justifiées",
    "non_justifiees": "non justifiées",
    "moyenne_generale_label": "Moyenne générale",
    "moyenne_eleve_header": "Élève",
    "moyenne_classe_header": "Classe",
    "ecrit_label": "Écrit",
    "oral_label": "Oral",
    "chef_etablissement": "Le chef d'établissement-adjoint",
}
