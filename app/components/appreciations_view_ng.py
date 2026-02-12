"""Appreciations view component — NiceGUI version."""

from __future__ import annotations

from nicegui import ui


def eleve_header(eleve: dict) -> None:
    """Render compact student header with key metrics on one line.

    Args:
        eleve: Student data dict.
    """
    genre = eleve.get("genre") or "?"
    absences = eleve.get("absences_demi_journees", 0) or 0
    retards = eleve.get("retards", 0) or 0
    matieres = eleve.get("matieres", [])
    nb_matieres = len(matieres)

    # Calculate averages
    moy_eleve = _calc_moyenne_eleve(matieres)
    moy_classe = _calc_moyenne_classe(matieres)

    with ui.row().classes("items-center gap-2 flex-wrap"):
        ui.label(
            f"{genre} · {absences} abs. · {retards} retard{'s' if retards != 1 else ''}"
            f" · {nb_matieres} matiere{'s' if nb_matieres != 1 else ''}"
        ).classes("text-body2 text-grey-5")

        if moy_eleve is not None:
            ui.label(f"Moy. eleve : {moy_eleve:.1f}/20").classes(
                "text-body2 text-weight-bold"
            )
        if moy_classe is not None:
            ui.label(f"Moy. classe : {moy_classe:.1f}/20").classes(
                "text-body2 text-grey-6"
            )


def _calc_moyenne_eleve(matieres: list[dict]) -> float | None:
    """Calculate student average across all subjects."""
    notes = [m["moyenne_eleve"] for m in matieres if m.get("moyenne_eleve") is not None]
    return sum(notes) / len(notes) if notes else None


def _calc_moyenne_classe(matieres: list[dict]) -> float | None:
    """Calculate class average across all subjects."""
    notes = [
        m["moyenne_classe"] for m in matieres if m.get("moyenne_classe") is not None
    ]
    return sum(notes) / len(notes) if notes else None


def appreciations(eleve: dict) -> None:
    """Render subject appreciations in a compact format.

    Designed for side-by-side layout with synthesis.

    Args:
        eleve: Full student data with matieres.
    """
    matieres = eleve.get("matieres", [])

    if not matieres:
        ui.label("Aucune matiere disponible.").classes("text-grey-6")
        return

    # Legend
    ui.label("Note eleve / ecart avec la classe").classes(
        "text-caption text-grey-6 q-mb-xs"
    )

    for matiere in matieres:
        with ui.card().classes("w-full q-mb-xs").style("padding: 8px 12px"):
            with ui.row().classes("w-full items-center justify-between"):
                # Left: subject + teacher
                with ui.column().classes("gap-0"):
                    ui.label(matiere["nom"]).classes("text-weight-bold text-body2")
                    prof = matiere.get("professeur", "")
                    if prof:
                        ui.label(prof).classes("text-caption text-grey-7")

                # Right: grade inline with delta
                note = matiere.get("moyenne_eleve")
                moy_classe = matiere.get("moyenne_classe")
                if note is not None:
                    with ui.row().classes("items-center gap-1"):
                        ui.label(f"{note}/20").classes("text-weight-bold text-body2")
                        if moy_classe is not None:
                            diff = note - moy_classe
                            delta_text = f"({diff:+.1f})"
                            delta_color = "text-green" if diff >= 0 else "text-red"
                            ui.label(delta_text).classes(f"text-caption {delta_color}")

            # Appreciation text
            appreciation = matiere.get("appreciation", "")
            if appreciation:
                ui.label(appreciation).classes("text-body2 italic q-mt-xs")


def appreciations_compact(eleve: dict, max_display: int = 5) -> None:
    """Render appreciations in ultra-compact format.

    Shows only subjects with appreciations, limited count.

    Args:
        eleve: Full student data with matieres.
        max_display: Maximum subjects to show.
    """
    matieres = eleve.get("matieres", [])
    with_appreciation = [m for m in matieres if m.get("appreciation")]

    if not with_appreciation:
        ui.label("Aucune appreciation disponible.").classes("text-caption text-grey-6")
        return

    for matiere in with_appreciation[:max_display]:
        note = matiere.get("moyenne_eleve", "-")
        ui.label(f"{matiere['nom']} ({note}/20)").classes("text-weight-bold text-body2")
        ui.label(matiere.get("appreciation", "")).classes("text-caption text-grey-7")
        ui.separator()

    remaining = len(with_appreciation) - max_display
    if remaining > 0:
        ui.label(f"... et {remaining} autre(s) matiere(s)").classes(
            "text-caption text-grey-6"
        )
