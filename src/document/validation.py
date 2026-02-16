"""Validation des données extraites d'un bulletin PDF."""

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
