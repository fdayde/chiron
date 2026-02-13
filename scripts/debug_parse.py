"""Debug script — run parsing on a PDF and dump diagnostic info.

Usage:
    python scripts/debug_parse.py                          # Parse raw PDF
    python scripts/debug_parse.py --anonymize              # Anonymize then parse
    python scripts/debug_parse.py --pdf path/to/file.pdf   # Custom PDF
"""

import argparse
import sys
import tempfile
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

from src.document.anonymizer import anonymize_pdf, extract_eleve_name  # noqa: E402
from src.document.parser import extract_pdf_content  # noqa: E402
from src.document.pdfplumber_parser import PdfplumberParser  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--pdf", default=str(ROOT / "data" / "demo" / "bulletin_fictif.pdf")
    )
    ap.add_argument("--anonymize", action="store_true", help="Anonymise avant parsing")
    args = ap.parse_args()

    pdf = Path(args.pdf)
    out_path = ROOT / "data" / "demo" / "diagnostic_parsing.txt"

    identity = extract_eleve_name(pdf)

    lines = []
    lines.append("=" * 70)
    lines.append(f"DIAGNOSTIC PARSING — {pdf.name}")
    lines.append(
        f"  mode: {'anonymisé puis parsé' if args.anonymize else 'parsing direct'}"
    )
    lines.append("=" * 70)

    # --- Name ---
    lines.append("")
    lines.append("--- NOM EXTRAIT ---")
    if identity:
        for k, v in identity.items():
            if k == "texte_complet":
                continue
            lines.append(f"  {k}: {v}")
    else:
        lines.append("  (aucun nom trouvé)")

    # --- Anonymize if requested ---
    parse_path = pdf
    if args.anonymize:
        lines.append("")
        lines.append("--- ANONYMISATION ---")
        try:
            anon_bytes = anonymize_pdf(pdf, "ELEVE_001")
            tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            tmp.write(anon_bytes)
            tmp.close()
            parse_path = Path(tmp.name)
            lines.append(f"  PDF anonymisé: {len(anon_bytes)} bytes")
            lines.append(f"  Fichier temp: {parse_path}")
        except Exception as e:
            lines.append(f"  ERREUR anonymisation: {e}")

    # --- Extract content ---
    content = extract_pdf_content(parse_path)

    # --- Raw text ---
    lines.append("")
    lines.append("--- TEXTE BRUT ---")
    lines.append(content.text)

    # --- Tables ---
    lines.append("")
    lines.append("--- TABLES ---")
    lines.append(f"{len(content.tables)} table(s)")
    for i, table in enumerate(content.tables):
        ncols = len(table[0]) if table else 0
        lines.append("")
        lines.append(f"Table {i}: {len(table)} lignes x {ncols} colonnes")
        lines.append("-" * 70)
        for j, row in enumerate(table):
            lines.append(f"  Row {j}:")
            for k, cell in enumerate(row):
                val = (cell or "(None)").replace("\n", " // ")
                if len(val) > 80:
                    val = val[:80] + "..."
                lines.append(f"    [{k}] {val}")

    # --- Parser result ---
    lines.append("")
    lines.append("--- RÉSULTAT DU PARSER ---")
    parser = PdfplumberParser()
    genre = identity.get("genre") if identity else None
    result = parser.parse(parse_path, "ELEVE_001", genre=genre)

    lines.append(f"  eleve_id: {result.eleve_id}")
    lines.append(f"  genre: {result.genre}")
    lines.append(f"  absences: {result.absences_demi_journees}")
    lines.append(f"  absences_justifiees: {result.absences_justifiees}")
    lines.append(f"  engagements: {result.engagements}")
    lines.append(f"  moyenne_generale: {result.moyenne_generale}")
    lines.append(f"  matieres: {len(result.matieres)} matière(s) extraite(s)")
    if result.matieres:
        for m in result.matieres:
            appr = (
                m.appreciation[:60] + "..."
                if len(m.appreciation) > 60
                else m.appreciation
            )
            lines.append(
                f"    - {m.nom}: élève={m.moyenne_eleve} classe={m.moyenne_classe} | {appr}"
            )
    else:
        lines.append("    >>> AUCUNE MATIÈRE — problème de parsing <<<")

    text = "\n".join(lines)
    out_path.write_text(text, encoding="utf-8")
    print(f"Diagnostic écrit: {out_path}")


if __name__ == "__main__":
    main()
