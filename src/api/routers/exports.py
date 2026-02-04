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
from src.document import ParserType, get_parser
from src.document.anonymizer import anonymize_pdf, extract_eleve_name
from src.llm.config import settings
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
            "Content-Disposition": (
                f"attachment; filename=syntheses_{classe_id}_T{trimestre}.csv"
            )
        },
    )


def _import_single_pdf(
    pdf_path: Path,
    classe_id: str,
    trimestre: int,
    pseudonymizer: Pseudonymizer,
    eleve_repo: EleveRepository,
    synthese_repo: SyntheseRepository,
    eleve_count: int = 0,
) -> dict:
    """Import a single PDF with the unified flow.

    Args:
        pdf_path: Path to the PDF file.
        classe_id: Class identifier.
        trimestre: Trimester number.
        pseudonymizer: Pseudonymizer instance.
        eleve_repo: Eleve repository.
        eleve_count: Current count for fallback ID generation.

    Returns:
        Dict with import results.
    """
    # 1. Extract student name from PDF (local, fast)
    identity = extract_eleve_name(pdf_path)

    if identity and identity.get("nom"):
        nom = identity["nom"]
        prenom = identity.get("prenom")
        genre = identity.get("genre")

        # 2. Create eleve_id and store mapping
        eleve_id = pseudonymizer.create_eleve_id(nom, prenom, classe_id)
        logger.info(f"Created/found eleve_id: {eleve_id} for {prenom} {nom}")

        # 3. Anonymize PDF
        pdf_bytes = anonymize_pdf(pdf_path, eleve_id)
        logger.info(f"PDF anonymized ({len(pdf_bytes)} bytes)")

    else:
        # Fallback: no name found, generate generic ID
        eleve_id = f"ELEVE_{eleve_count + 1:03d}"
        genre = None
        logger.warning(f"No name found in PDF, using fallback ID: {eleve_id}")

        # Use original PDF (can't anonymize without a name)
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

    # 4. Parse PDF (pdfplumber or Mistral OCR)
    parser_type = ParserType(settings.pdf_parser_type.lower())
    parser = get_parser(parser_type)

    if parser_type == ParserType.MISTRAL_OCR:
        # Mistral OCR accepts bytes directly
        eleve = parser.parse(pdf_bytes, eleve_id, genre=genre)
    else:
        # pdfplumber needs a file path, save anonymized PDF temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_bytes)
            tmp_anon_path = Path(tmp.name)

        try:
            eleve = parser.parse(tmp_anon_path, eleve_id, genre=genre)
        finally:
            tmp_anon_path.unlink(missing_ok=True)

    # 5. Set trimestre and classe
    eleve.trimestre = trimestre
    eleve.classe = classe_id

    # 6. Store in database (overwrite if exists)
    was_overwritten = False
    if eleve_repo.exists(eleve_id, trimestre):
        eleve_repo.delete(eleve_id, trimestre)
        synthese_repo.delete_for_eleve(eleve_id, trimestre)
        was_overwritten = True
        logger.info(f"Overwriting existing data for {eleve_id} T{trimestre}")

    eleve_repo.create(eleve)
    return {
        "status": "overwritten" if was_overwritten else "imported",
        "eleve_id": eleve_id,
    }


@router.post("/import/pdf")
async def import_pdf(
    classe_id: str,
    trimestre: int,
    file: UploadFile = File(...),
    classe_repo: ClasseRepository = Depends(get_classe_repo),
    eleve_repo: EleveRepository = Depends(get_eleve_repo),
    synthese_repo: SyntheseRepository = Depends(get_synthese_repo),
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
        result = _import_single_pdf(
            pdf_path=tmp_path,
            classe_id=classe_id,
            trimestre=trimestre,
            pseudonymizer=pseudonymizer,
            eleve_repo=eleve_repo,
            synthese_repo=synthese_repo,
            eleve_count=0,
        )

        was_overwritten = result["status"] == "overwritten"
        return {
            "status": "success",
            "filename": file.filename,
            "classe_id": classe_id,
            "trimestre": trimestre,
            "parsed_count": 1,
            "imported_count": 1,
            "overwritten_count": 1 if was_overwritten else 0,
            "eleve_ids": [result["eleve_id"]],
            "overwritten_ids": [result["eleve_id"]] if was_overwritten else [],
        }

    except Exception as e:
        logger.error(f"Error importing {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

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
    synthese_repo: SyntheseRepository = Depends(get_synthese_repo),
    pseudonymizer: Pseudonymizer = Depends(get_pseudonymizer),
):
    """Import multiple PDF bulletins."""
    # Validate class exists or create it
    classe = classe_repo.get(classe_id)
    if not classe:
        from src.storage.repositories.classe import Classe

        classe = Classe(classe_id=classe_id, nom=classe_id)
        classe_repo.create(classe)

    results = []
    total_imported = 0
    total_overwritten = 0

    for i, file in enumerate(files):
        tmp_path = None
        try:
            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = Path(tmp.name)

            result = _import_single_pdf(
                pdf_path=tmp_path,
                classe_id=classe_id,
                trimestre=trimestre,
                pseudonymizer=pseudonymizer,
                eleve_repo=eleve_repo,
                synthese_repo=synthese_repo,
                eleve_count=total_imported + i,
            )

            was_overwritten = result["status"] == "overwritten"
            total_imported += 1
            if was_overwritten:
                total_overwritten += 1

            results.append(
                {
                    "filename": file.filename,
                    "status": "overwritten" if was_overwritten else "imported",
                    "eleve_id": result["eleve_id"],
                }
            )

        except Exception as e:
            logger.error(f"Error importing {file.filename}: {e}")
            results.append(
                {
                    "filename": file.filename,
                    "status": "error",
                    "error": str(e),
                }
            )

        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

    return {
        "classe_id": classe_id,
        "trimestre": trimestre,
        "total_imported": total_imported,
        "total_overwritten": total_overwritten,
        "files": results,
    }
