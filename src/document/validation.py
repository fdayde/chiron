"""Validation des données extraites d'un bulletin PDF."""

import re
from dataclasses import dataclass, field

from src.core.models import EleveExtraction


@dataclass
class ValidationResult:
    """Résultat de validation avec erreurs bloquantes et warnings."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


def validate_extraction(eleve: EleveExtraction) -> ValidationResult:
    """Valide une extraction d'élève après parsing.

    Args:
        eleve: Données extraites du PDF.

    Returns:
        ValidationResult avec erreurs bloquantes et warnings.
    """
    result = ValidationResult()

    # Bloquant : aucune matière détectée
    if len(eleve.matieres) == 0:
        result.errors.append(
            "Aucune matière détectée — ce PDF n'est probablement pas un bulletin scolaire"
        )

    # Warning : matières sans note
    if eleve.matieres:
        sans_note = [m.nom for m in eleve.matieres if m.moyenne_eleve is None]
        if sans_note:
            result.warnings.append(
                f"{len(sans_note)} matière(s) sans note : {', '.join(sans_note[:5])}"
            )

    # Warning : matières sans appréciation
    if eleve.matieres:
        sans_appre = [m.nom for m in eleve.matieres if not m.appreciation]
        if sans_appre:
            result.warnings.append(
                f"{len(sans_appre)} matière(s) sans appréciation : {', '.join(sans_appre[:5])}"
            )

    return result


def _extract_level(classe_str: str) -> str | None:
    """Extrait le niveau (ex: '5') depuis un identifiant de classe.

    Gère les formats '5E', '5E_2024-2025', '3A', etc.

    Returns:
        Le niveau (chiffre) ou None si non détecté.
    """
    match = re.match(r"(\d+)", classe_str)
    return match.group(1) if match else None


def check_classe_mismatch(pdf_classe: str | None, user_classe_id: str) -> str | None:
    """Compare le niveau de classe extrait du PDF avec celui saisi par l'utilisateur.

    Args:
        pdf_classe: Classe extraite du PDF (ex: '5E'), ou None si non détectée.
        user_classe_id: Identifiant de classe saisi (ex: '5E_2024-2025').

    Returns:
        Message de warning si mismatch, None sinon.
    """
    if not pdf_classe:
        return None

    pdf_level = _extract_level(pdf_classe)
    user_level = _extract_level(user_classe_id)

    if not pdf_level or not user_level:
        return None

    if pdf_level != user_level:
        return (
            f"Le bulletin semble correspondre à une classe de {pdf_classe}, "
            f"mais la classe sélectionnée est {user_classe_id}"
        )

    return None
