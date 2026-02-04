"""Import/Export router."""

import csv
import io
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from src.api.dependencies import (
    get_classe_repo,
    get_eleve_repo,
    get_pseudonymizer,
    get_synthese_repo,
)
from src.document import get_parser
from src.privacy.pseudonymizer import Pseudonymizer
from src.storage.repositories.classe import ClasseRepository
from src.storage.repositories.eleve import EleveRepository
from src.storage.repositories.synthese import SyntheseRepository

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/export/csv")
def export_csv(
    classe_id: str,
    trimestre: int,
    classe_repo: ClasseRepository = Depends(get_classe_repo),
    eleve_repo: EleveRepository = Depends(get_eleve_repo),
    synthese_repo: SyntheseRepository = Depends(get_synthese_repo),
    pseudonymizer: Pseudonymizer = Depends(get_pseudonymizer),
):
    """Export validated syntheses as CSV."""
    classe = classe_repo.get(classe_id)
    if not classe:
        raise HTTPException(status_code=404, detail="Class not found")

    validated = synthese_repo.get_validated(classe_id, trimestre)

    # Build CSV content using csv module for proper escaping
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_ALL)

    # Header
    writer.writerow(
        ["eleve_id", "synthese_texte", "posture_generale", "alertes", "reussites"]
    )

    # Data rows
    for item in validated:
        synthese = item["synthese"]
        # Depseudonymize the text (scoped by classe_id for security)
        text = pseudonymizer.depseudonymize_text(synthese.synthese_texte, classe_id)
        alertes = "; ".join(f"{a.matiere}: {a.description}" for a in synthese.alertes)
        reussites = "; ".join(
            f"{r.matiere}: {r.description}" for r in synthese.reussites
        )
        writer.writerow(
            [item["eleve_id"], text, synthese.posture_generale, alertes, reussites]
        )

    csv_content = output.getvalue()

    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=syntheses_{classe_id}_T{trimestre}.csv"
        },
    )


@router.post("/import/pdf")
async def import_pdf(
    classe_id: str,
    trimestre: int,
    file: UploadFile = File(...),
    classe_repo: ClasseRepository = Depends(get_classe_repo),
    eleve_repo: EleveRepository = Depends(get_eleve_repo),
    pseudonymizer: Pseudonymizer = Depends(get_pseudonymizer),
):
    """Import a PDF bulletin and extract student data."""
    # Validate class exists or create it
    classe = classe_repo.get(classe_id)
    if not classe:
        from src.storage.repositories.classe import Classe

        classe = Classe(classe_id=classe_id, nom=classe_id)
        classe_repo.create(classe)

    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        # Parse PDF
        parser = get_parser()
        eleves = parser.parse(tmp_path)

        logger.info(f"Parser returned {len(eleves)} eleve(s) from {file.filename}")
        for i, e in enumerate(eleves):
            logger.info(
                f"  [{i}] nom={e.nom}, prenom={e.prenom}, raw_text_len={len(e.raw_text or '')}"
            )

        imported = []
        skipped = []
        for eleve in eleves:
            # Set trimestre and classe
            eleve.trimestre = trimestre
            eleve.classe = classe_id

            # Pseudonymize
            if eleve.nom:
                eleve_pseudo = pseudonymizer.pseudonymize(eleve, classe_id)
            else:
                eleve_pseudo = eleve
                eleve_pseudo.eleve_id = f"ELEVE_{len(imported) + len(skipped) + 1:03d}"

            # Save to database (check by eleve_id AND trimestre)
            if not eleve_repo.exists(eleve_pseudo.eleve_id, trimestre):
                eleve_repo.create(eleve_pseudo)
                imported.append(eleve_pseudo.eleve_id)
            else:
                skipped.append(eleve_pseudo.eleve_id)

        return {
            "status": "success",
            "filename": file.filename,
            "classe_id": classe_id,
            "trimestre": trimestre,
            "parsed_count": len(eleves),
            "imported_count": len(imported),
            "skipped_count": len(skipped),
            "eleve_ids": imported,
            "skipped_ids": skipped,
        }

    finally:
        # Cleanup temp file
        tmp_path.unlink(missing_ok=True)


@router.post("/import/pdf/batch")
async def import_pdf_batch(
    classe_id: str,
    trimestre: int,
    files: list[UploadFile] = File(...),
    classe_repo: ClasseRepository = Depends(get_classe_repo),
    eleve_repo: EleveRepository = Depends(get_eleve_repo),
    pseudonymizer: Pseudonymizer = Depends(get_pseudonymizer),
):
    """Import multiple PDF bulletins."""
    results = []
    total_imported = 0

    for file in files:
        tmp_path = None
        try:
            # Reuse single import logic
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = Path(tmp.name)

            parser = get_parser()
            eleves = parser.parse(tmp_path)

            imported = []
            for eleve in eleves:
                eleve.trimestre = trimestre
                eleve.classe = classe_id

                if eleve.nom:
                    eleve_pseudo = pseudonymizer.pseudonymize(eleve, classe_id)
                else:
                    eleve_pseudo = eleve
                    eleve_pseudo.eleve_id = (
                        f"ELEVE_{total_imported + len(imported) + 1:03d}"
                    )

                # Check by eleve_id AND trimestre
                if not eleve_repo.exists(eleve_pseudo.eleve_id, trimestre):
                    eleve_repo.create(eleve_pseudo)
                    imported.append(eleve_pseudo.eleve_id)

            results.append(
                {
                    "filename": file.filename,
                    "status": "success",
                    "imported_count": len(imported),
                }
            )
            total_imported += len(imported)

        except Exception as e:
            results.append(
                {
                    "filename": file.filename,
                    "status": "error",
                    "error": str(e),
                }
            )
        finally:
            # Always cleanup temp file, even if parsing fails
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

    return {
        "classe_id": classe_id,
        "trimestre": trimestre,
        "total_imported": total_imported,
        "files": results,
    }
