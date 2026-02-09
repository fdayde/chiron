"""Appreciations view component — NiceGUI version."""

from __future__ import annotations

from components.metric_card_ng import metric_card
from nicegui import ui


def eleve_header(eleve: dict) -> None:
    """Render compact student header with key metrics.

    Args:
        eleve: Student data dict.
    """
    with ui.row().classes("gap-4"):
        metric_card("Genre", eleve.get("genre") or "?")
        metric_card("Absences", eleve.get("absences_demi_journees", 0) or 0)
        metric_card("Retards", eleve.get("retards", 0) or 0)
        metric_card("Matieres", len(eleve.get("matieres", [])))


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

    for matiere in matieres:
        with ui.card().classes("w-full p-3 q-mb-xs"):
            with ui.row().classes("w-full items-start justify-between"):
                # Left: subject + teacher
                with ui.column().classes("gap-0"):
                    ui.label(matiere["nom"]).classes("text-weight-bold")
                    prof = matiere.get("professeur", "")
                    if prof:
                        ui.label(prof).classes("text-caption text-grey-7")

                # Right: grade with delta
                note = matiere.get("moyenne_eleve")
                moy_classe = matiere.get("moyenne_classe")
                if note is not None:
                    delta = None
                    delta_color = "positive"
                    if moy_classe is not None:
                        diff = note - moy_classe
                        delta = f"{diff:+.1f}"
                        delta_color = "positive" if diff >= 0 else "negative"
                    metric_card(
                        "Note", f"{note}/20", delta=delta, delta_color=delta_color
                    )

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
