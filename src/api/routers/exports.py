"""Import/Export router."""

import io
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
from src.document.bulletin_parser import BulletinParser
from src.privacy.pseudonymizer import Pseudonymizer
from src.storage.repositories.classe import ClasseRepository
from src.storage.repositories.eleve import EleveRepository
from src.storage.repositories.synthese import SyntheseRepository

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

    # Build CSV content
    lines = ["eleve_id;synthese_texte;posture_generale;alertes;reussites"]
    for item in validated:
        synthese = item["synthese"]
        # Depseudonymize the text
        text = pseudonymizer.depseudonymize_text(synthese.synthese_texte)
        # Escape semicolons and quotes
        text = text.replace('"', '""')
        alertes = "; ".join(f"{a.matiere}: {a.description}" for a in synthese.alertes)
        reussites = "; ".join(
            f"{r.matiere}: {r.description}" for r in synthese.reussites
        )
        lines.append(
            f'"{item["eleve_id"]}";"{text}";"{synthese.posture_generale}";"{alertes}";"{reussites}"'
        )

    csv_content = "\n".join(lines)

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
        parser = BulletinParser()
        eleves = parser.parse(tmp_path)

        imported = []
        for eleve in eleves:
            # Set trimestre and classe
            eleve.trimestre = trimestre
            eleve.classe = classe_id

            # Pseudonymize
            if eleve.nom:
                eleve_pseudo = pseudonymizer.pseudonymize(eleve, classe_id)
            else:
                eleve_pseudo = eleve
                eleve_pseudo.eleve_id = f"ELEVE_{len(imported) + 1:03d}"

            # Save to database
            if not eleve_repo.exists(eleve_pseudo.eleve_id):
                eleve_repo.create(eleve_pseudo)
                imported.append(eleve_pseudo.eleve_id)

        return {
            "status": "success",
            "filename": file.filename,
            "classe_id": classe_id,
            "trimestre": trimestre,
            "imported_count": len(imported),
            "eleve_ids": imported,
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
        try:
            # Reuse single import logic
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = Path(tmp.name)

            parser = BulletinParser()
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

                if not eleve_repo.exists(eleve_pseudo.eleve_id):
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

            tmp_path.unlink(missing_ok=True)

        except Exception as e:
            results.append(
                {
                    "filename": file.filename,
                    "status": "error",
                    "error": str(e),
                }
            )

    return {
        "classe_id": classe_id,
        "trimestre": trimestre,
        "total_imported": total_imported,
        "files": results,
    }
