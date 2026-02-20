"""Visualisation debug des zones detectees dans un PDF.

Genere un PDF annote avec des rectangles colores sur les zones
correspondant aux champs extraits par le template YAML.
"""

import logging
import re
from pathlib import Path

import fitz  # PyMuPDF
import yaml

from src.document.parser import extract_pdf_content
from src.document.yaml_template_parser import YamlTemplateParser

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"

# Couleurs RGBA pour chaque zone (R, G, B, alpha)
ZONE_COLORS: dict[str, tuple[float, float, float, float]] = {
    "eleve": (1.0, 0.0, 0.0, 0.3),
    "genre": (0.2, 0.6, 1.0, 0.3),
    "absences": (1.0, 0.4, 0.4, 0.3),
    "retards": (1.0, 0.6, 0.2, 0.3),
    "engagements": (0.4, 0.8, 0.4, 0.3),
    "moyenne_generale": (0.8, 0.2, 0.8, 0.3),
    "annee_scolaire": (0.2, 0.8, 0.8, 0.3),
    "trimestre": (0.6, 0.6, 0.2, 0.3),
    "matiere": (0.0, 0.5, 1.0, 0.2),
    "prof_principal": (1.0, 0.4, 0.7, 0.3),
    "classe": (1.0, 0.6, 0.0, 0.3),
    "professeur": (0.8, 0.6, 1.0, 0.25),
}

DEFAULT_COLOR = (0.5, 0.5, 0.5, 0.3)


def generate_debug_pdf(
    pdf_path: Path | str,
    template_name: str = "pronote_standard",
) -> bytes:
    """Genere un PDF annote montrant les zones detectees.

    Args:
        pdf_path: Chemin vers le PDF original.
        template_name: Nom du template YAML a utiliser.

    Returns:
        Bytes du PDF annote.
    """
    pdf_path = Path(pdf_path)

    # Charger le template
    template_path = TEMPLATES_DIR / f"{template_name}.yaml"
    with open(template_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    fields = config.get("fields", {})

    # Extraire le texte et les tables
    content = extract_pdf_content(pdf_path)
    raw_text = content.text or ""

    # Parser les tables via YamlTemplateParser pour obtenir matieres + footer
    parser = YamlTemplateParser(template_name)
    matieres, _footer = parser._parse_pronote_tables(content.tables)

    # Construire la liste des textes a chercher dans le PDF
    search_targets: list[tuple[str, str]] = []  # (field_name, search_text)

    # 1. Zone eleve - Strategie 1 : "Eleve : NOM"
    eleve_match = re.search(r"[ÉE]l[èe]ve\s*:\s*[^\n]+", raw_text, re.IGNORECASE)
    if eleve_match:
        search_targets.append(("eleve", eleve_match.group(0).strip()))
    else:
        # Strategie 2 : "NOM Prenom" avant "Ne(e) le" (PRONOTE reel)
        eleve_match2 = re.search(
            r"([A-ZÀ-Ü][-A-ZÀ-Ü]+\s+[A-Za-zÀ-ü][a-zà-ü]+(?:-[A-Za-zÀ-ü][a-zà-ü]+)*)\s*\n\s*Né[e]?\s+le",
            raw_text,
        )
        if eleve_match2:
            search_targets.append(("eleve", eleve_match2.group(1).strip()))

    # 2. Champs du template YAML
    for field_name, spec in fields.items():
        # Skip absences_justifiees (meme zone que absences)
        if field_name == "absences_justifiees":
            continue
        search_text = _get_search_text(raw_text, spec)
        if search_text:
            search_targets.append((field_name, search_text))

    # 3. Matieres (noms extraits des tables)
    for mat in matieres:
        search_targets.append(("matiere", mat.nom))
        # Noms de profs extraits des tables (peut etre "M. X, Mme Y")
        if mat.professeur:
            for prof in mat.professeur.split(", "):
                search_targets.append(("professeur", prof))

    # Annoter le PDF avec PyMuPDF
    doc = fitz.open(pdf_path)

    for page in doc:
        for field_name, search_text in search_targets:
            rects = page.search_for(search_text)
            if not rects:
                continue

            r, g, b, a = ZONE_COLORS.get(field_name, DEFAULT_COLOR)
            for rect in rects:
                shape = page.new_shape()
                shape.draw_rect(rect)
                shape.finish(color=(r, g, b), fill=(r, g, b), fill_opacity=a)
                shape.commit()

    # Legende en bas de la premiere page
    if doc.page_count > 0:
        first_page = doc[0]
        # Dedupliquer les noms de zones pour la legende
        legend_names = dict.fromkeys(name for name, _ in search_targets)
        y = first_page.rect.height - 15
        x = 10
        for name in legend_names:
            r, g, b, _ = ZONE_COLORS.get(name, DEFAULT_COLOR)
            first_page.insert_text(
                (x, y),
                f"■ {name}",
                fontsize=7,
                fontname="helv",
                color=(r, g, b),
            )
            x += 90
            if x > first_page.rect.width - 100:
                x = 10
                y -= 12

    result = doc.tobytes()
    doc.close()
    return result


def _get_search_text(raw_text: str, spec: dict) -> str | None:
    """Determine le texte a rechercher dans le PDF pour un champ donne."""
    method = spec.get("method")

    if method == "key_value":
        key = spec.get("key", "")
        # Capturer la ligne complete : "Cle : valeur complete"
        match = re.search(rf"({key}\s*:\s*[^\n]+)", raw_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    if method == "regex":
        pattern = spec.get("pattern", "")
        match = re.search(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(0).strip()
        return None

    return None
