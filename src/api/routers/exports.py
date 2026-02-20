"""Router d'import/export."""

import csv
import io
import logging
import re
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from src.api.dependencies import (
    get_classe_repo,
    get_eleve_repo,
    get_or_404,
    get_pseudonymizer,
    get_synthese_repo,
)
from src.core.exceptions import ParserError
from src.core.models import EleveExtraction
from src.document import get_parser
from src.document.anonymizer import (
    extract_eleve_name,
    ner_check_student_names,
)
from src.document.validation import check_classe_mismatch, validate_extraction
from src.privacy.pseudonymizer import Pseudonymizer
from src.services.shared import ensure_classe_exists, temp_pdf_file
from src.storage.repositories.classe import ClasseRepository
from src.storage.repositories.eleve import EleveRepository
from src.storage.repositories.synthese import SyntheseRepository

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_PDF_SIZE_MB = 20
MAX_BATCH_FILES = 50


async def _validate_pdf_upload(file: UploadFile) -> bytes:
    """Valide et lit un fichier PDF uploadé.

    Args:
        file: Fichier uploadé.

    Returns:
        Contenu du fichier en bytes.

    Raises:
        HTTPException: Si le fichier est invalide.
    """
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail=f"Type de fichier invalide : {file.content_type}. Seuls les PDF sont acceptés.",
        )

    content = await file.read()
    max_bytes = MAX_PDF_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"Fichier trop volumineux ({len(content) // (1024 * 1024)} Mo). Maximum : {MAX_PDF_SIZE_MB} Mo.",
        )

    return content


@router.get("/export/csv")
def export_csv(
    classe_id: str,
    trimestre: int,
    classe_repo: ClasseRepository = Depends(get_classe_repo),
    eleve_repo: EleveRepository = Depends(get_eleve_repo),
    synthese_repo: SyntheseRepository = Depends(get_synthese_repo),
    pseudonymizer: Pseudonymizer = Depends(get_pseudonymizer),
):
    """Exporter les synthèses validées en CSV."""
    classe = get_or_404(classe_repo, classe_id, entity_name="Class")
    classe_nom = classe.nom.replace(" ", "_") if classe.nom else classe_id

    validated = synthese_repo.get_validated(classe_id, trimestre)

    # Build CSV content using csv module for proper escaping
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_ALL)

    # Build real-name lookup from pseudonymizer
    mappings = pseudonymizer.list_mappings(classe_id)
    name_by_id = {
        m["eleve_id"]: (m.get("nom_original", ""), m.get("prenom_original", ""))
        for m in mappings
    }

    # Header
    writer.writerow(
        ["nom", "prenom", "synthese_texte", "posture_generale", "alertes", "reussites"]
    )

    # Data rows
    for item in validated:
        synthese = item["synthese"]
        eleve_id = item["eleve_id"]
        nom, prenom = name_by_id.get(eleve_id, ("", ""))
        # Depseudonymize the text (scoped by classe_id for security)
        text = pseudonymizer.depseudonymize_text(synthese.synthese_texte, classe_id)
        alertes = "; ".join(f"{a.matiere}: {a.description}" for a in synthese.alertes)
        reussites = "; ".join(
            f"{r.matiere}: {r.description}" for r in synthese.reussites
        )
        writer.writerow(
            [nom, prenom, text, synthese.posture_generale, alertes, reussites]
        )

    csv_content = output.getvalue()

    # Add UTF-8 BOM for Excel compatibility
    csv_bytes = ("\ufeff" + csv_content).encode("utf-8")

    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f"attachment; filename=syntheses_{classe_nom}_T{trimestre}_{date.today().isoformat()}.csv"
            )
        },
    )


def _pseudonymize_extraction(
    eleve: EleveExtraction,
    identity: dict,
    eleve_id: str,
) -> None:
    """Pseudonymise les champs texte d'une extraction en remplaçant le nom par eleve_id.

    Remplace toutes les variantes du nom de l'élève (nom complet, prénom seul,
    nom seul) dans les appréciations et le texte brut.

    Args:
        eleve: Extraction à pseudonymiser (modifiée in-place).
        identity: Dict avec 'nom', 'prenom', 'nom_complet'.
        eleve_id: Identifiant pseudonyme (ex: "ELEVE_001").
    """
    nom = identity.get("nom", "")
    prenom = identity.get("prenom", "")
    nom_complet = identity.get("nom_complet", "")

    # Build variants to replace (longest first to avoid partial matches)
    variants = []
    if nom_complet:
        variants.append(nom_complet)
    if prenom and nom:
        variants.append(f"{prenom} {nom}")
        variants.append(f"{nom} {prenom}")
    if nom:
        variants.append(nom)
    if prenom:
        variants.append(prenom)

    # Deduplicate while preserving order (longest-first)
    seen: set[str] = set()
    unique_variants: list[str] = []
    for v in variants:
        v_lower = v.lower()
        if v_lower not in seen:
            seen.add(v_lower)
            unique_variants.append(v)

    if not unique_variants:
        return

    # Compile patterns once
    patterns = [
        re.compile(rf"\b{re.escape(v)}\b", re.IGNORECASE) for v in unique_variants
    ]

    def replace_names(text: str) -> str:
        if not text:
            return text
        for pattern in patterns:
            text = pattern.sub(eleve_id, text)
        return text

    # Pseudonymize appreciations
    for matiere in eleve.matieres:
        if matiere.appreciation:
            matiere.appreciation = replace_names(matiere.appreciation)

    # Pseudonymize appreciation_generale if present
    if eleve.appreciation_generale:
        eleve.appreciation_generale = replace_names(eleve.appreciation_generale)

    # NER safety net : vérifier les appréciations après le pass regex
    nom_parts_set = {p.lower() for p in [nom, prenom] if p and len(p) > 1}
    if nom_parts_set:
        appreciation_texts = [m.appreciation for m in eleve.matieres if m.appreciation]
        remaining = ner_check_student_names(appreciation_texts, nom_parts_set)
        if remaining:
            logger.warning("NER safety net: found %s in appreciations", remaining)
            for variant in remaining:
                pattern = re.compile(rf"\b{re.escape(variant)}\b", re.IGNORECASE)
                for matiere in eleve.matieres:
                    if matiere.appreciation:
                        matiere.appreciation = pattern.sub(
                            eleve_id, matiere.appreciation
                        )


def _import_single_pdf(
    pdf_path: Path,
    classe_id: str,
    trimestre: int,
    pseudonymizer: Pseudonymizer,
    eleve_repo: EleveRepository,
    synthese_repo: SyntheseRepository,
    force_overwrite: bool = True,
    classe_nom: str | None = None,
) -> dict:
    """Importe un PDF unique avec le flux unifié.

    Args:
        pdf_path: Chemin vers le fichier PDF.
        classe_id: Identifiant de la classe.
        trimestre: Numéro du trimestre.
        pseudonymizer: Instance du pseudonymiseur.
        eleve_repo: Repository des élèves.
        synthese_repo: Repository des synthèses.
        force_overwrite: Si False, les élèves existants sont ignorés.
        classe_nom: Nom lisible de la classe (pour les messages de warning).

    Returns:
        Dict avec les résultats de l'import.

    Raises:
        ParserError: Si le nom de l'élève n'est pas détecté dans le PDF.
    """
    # 1. Extract student name from PDF (local, fast)
    identity = extract_eleve_name(pdf_path)

    if not identity or not identity.get("nom"):
        raise ParserError(
            "Nom de l'élève non détecté dans le PDF",
            details={"filename": pdf_path.name},
        )

    nom = identity["nom"]
    prenom = identity.get("prenom")
    genre = identity.get("genre")

    # 2. Create eleve_id and store mapping
    eleve_id = pseudonymizer.create_eleve_id(nom, prenom, classe_id)
    logger.info(f"Created/found eleve_id: {eleve_id} for {prenom} {nom}")

    # 3. Parse PDF
    parser = get_parser()

    eleve = parser.parse(pdf_path, eleve_id, genre=genre)
    _pseudonymize_extraction(eleve, identity, eleve_id)
    logger.info(f"Text fields pseudonymized for {eleve_id}")

    # 4. Validate extraction
    validation = validate_extraction(eleve)
    if not validation.is_valid:
        raise ParserError(
            validation.errors[0],
            details={"filename": pdf_path.name, "all_errors": validation.errors},
        )

    # 4b. Check classe mismatch (PDF vs user selection)
    logger.info(
        f"Classe check: pdf_classe={eleve.classe!r}, user_classe_id={classe_id!r}"
    )
    classe_warning = check_classe_mismatch(
        eleve.classe, classe_id, classe_nom=classe_nom
    )
    if classe_warning:
        validation.warnings.append(classe_warning)

    # 5. Set trimestre and classe
    eleve.trimestre = trimestre
    eleve.classe = classe_id

    # 6. Store in database (overwrite if exists)
    was_overwritten = False
    if eleve_repo.exists(eleve_id, trimestre):
        if not force_overwrite:
            return {
                "status": "skipped",
                "eleve_id": eleve_id,
                "warnings": validation.warnings,
            }
        eleve_repo.delete(eleve_id, trimestre)
        synthese_repo.delete_for_eleve(eleve_id, trimestre)
        was_overwritten = True
        logger.info(f"Overwriting existing data for {eleve_id} T{trimestre}")

    eleve_repo.create(eleve)
    return {
        "status": "overwritten" if was_overwritten else "imported",
        "eleve_id": eleve_id,
        "warnings": validation.warnings,
    }


@router.post("/import/pdf/check")
async def check_pdf_duplicates(
    classe_id: str,
    trimestre: int,
    files: list[UploadFile] = File(...),
    eleve_repo: EleveRepository = Depends(get_eleve_repo),
    pseudonymizer: Pseudonymizer = Depends(get_pseudonymizer),
):
    """Vérifie les doublons avant import.

    Pour chaque fichier PDF, extrait le nom de l'élève (regex rapide, pas de NER)
    et vérifie s'il existe déjà dans la base pour ce trimestre.
    """
    conflicts = []
    new = []
    unreadable = []

    for file in files:
        try:
            content = await _validate_pdf_upload(file)

            with temp_pdf_file(content) as tmp_path:
                identity = extract_eleve_name(tmp_path)
                if not identity or not identity.get("nom"):
                    unreadable.append(
                        {
                            "filename": file.filename,
                            "error": "Nom de l'élève non détecté",
                        }
                    )
                    continue

                nom = identity["nom"]
                prenom = identity.get("prenom")

                existing_id = pseudonymizer._get_existing_mapping(
                    nom, prenom, classe_id
                )
                if existing_id and eleve_repo.exists(existing_id, trimestre):
                    conflicts.append(
                        {
                            "filename": file.filename,
                            "prenom": prenom,
                            "nom": nom,
                            "eleve_id": existing_id,
                        }
                    )
                else:
                    new.append(
                        {"filename": file.filename, "prenom": prenom, "nom": nom}
                    )

        except Exception as e:
            unreadable.append({"filename": file.filename, "error": str(e)})

    return {"conflicts": conflicts, "new": new, "unreadable": unreadable}


@router.post("/import/pdf")
async def import_pdf(
    classe_id: str,
    trimestre: int,
    force_overwrite: bool = True,
    file: UploadFile = File(...),
    classe_repo: ClasseRepository = Depends(get_classe_repo),
    eleve_repo: EleveRepository = Depends(get_eleve_repo),
    synthese_repo: SyntheseRepository = Depends(get_synthese_repo),
    pseudonymizer: Pseudonymizer = Depends(get_pseudonymizer),
):
    """Importer un bulletin PDF et extraire les données de l'élève."""
    ensure_classe_exists(classe_repo, classe_id)
    classe = classe_repo.get(classe_id)
    classe_nom = classe.nom if classe else None

    content = await _validate_pdf_upload(file)

    try:
        with temp_pdf_file(content) as tmp_path:
            result = _import_single_pdf(
                pdf_path=tmp_path,
                classe_id=classe_id,
                trimestre=trimestre,
                pseudonymizer=pseudonymizer,
                eleve_repo=eleve_repo,
                synthese_repo=synthese_repo,
                force_overwrite=force_overwrite,
                classe_nom=classe_nom,
            )

            was_overwritten = result["status"] == "overwritten"
            was_skipped = result["status"] == "skipped"
            return {
                "status": "success",
                "filename": file.filename,
                "classe_id": classe_id,
                "trimestre": trimestre,
                "parsed_count": 1,
                "imported_count": 0 if was_skipped else 1,
                "overwritten_count": 1 if was_overwritten else 0,
                "skipped_count": 1 if was_skipped else 0,
                "eleve_ids": [] if was_skipped else [result["eleve_id"]],
                "overwritten_ids": [result["eleve_id"]] if was_overwritten else [],
                "skipped_ids": [result["eleve_id"]] if was_skipped else [],
                "warnings": result.get("warnings", []),
            }

    except ParserError as e:
        raise HTTPException(status_code=422, detail=e.message) from e

    except Exception as e:
        logger.error(f"Error importing {file.filename}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de l'import du PDF. Consultez les logs du serveur.",
        ) from e


@router.post("/import/pdf/batch")
async def import_pdf_batch(
    classe_id: str,
    trimestre: int,
    force_overwrite: bool = True,
    files: list[UploadFile] = File(...),
    classe_repo: ClasseRepository = Depends(get_classe_repo),
    eleve_repo: EleveRepository = Depends(get_eleve_repo),
    synthese_repo: SyntheseRepository = Depends(get_synthese_repo),
    pseudonymizer: Pseudonymizer = Depends(get_pseudonymizer),
):
    """Importer plusieurs bulletins PDF."""
    # Validate batch size
    if len(files) > MAX_BATCH_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Trop de fichiers ({len(files)}). Maximum : {MAX_BATCH_FILES}.",
        )

    ensure_classe_exists(classe_repo, classe_id)
    classe = classe_repo.get(classe_id)
    classe_nom = classe.nom if classe else None

    results = []
    total_imported = 0
    total_overwritten = 0
    total_skipped = 0

    for _i, file in enumerate(files):
        try:
            content = await _validate_pdf_upload(file)

            with temp_pdf_file(content) as tmp_path:
                result = _import_single_pdf(
                    pdf_path=tmp_path,
                    classe_id=classe_id,
                    trimestre=trimestre,
                    pseudonymizer=pseudonymizer,
                    eleve_repo=eleve_repo,
                    synthese_repo=synthese_repo,
                    force_overwrite=force_overwrite,
                    classe_nom=classe_nom,
                )

            was_overwritten = result["status"] == "overwritten"
            was_skipped = result["status"] == "skipped"
            if was_skipped:
                total_skipped += 1
            else:
                total_imported += 1
            if was_overwritten:
                total_overwritten += 1

            results.append(
                {
                    "filename": file.filename,
                    "status": result["status"],
                    "eleve_id": result["eleve_id"],
                    "warnings": result.get("warnings", []),
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

    return {
        "classe_id": classe_id,
        "trimestre": trimestre,
        "total_imported": total_imported,
        "total_overwritten": total_overwritten,
        "total_skipped": total_skipped,
        "files": results,
    }
