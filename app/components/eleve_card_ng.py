"""Student card component — NiceGUI version."""

from __future__ import annotations

from components.metric_card_ng import metric_card
from nicegui import ui


def eleve_card(eleve: dict, synthese: dict | None = None) -> None:
    """Render a student information card.

    Args:
        eleve: Student data dict.
        synthese: Optional synthesis data dict.
    """
    with ui.card().classes("w-full p-4"):
        with ui.row().classes("w-full items-center justify-between"):
            # Left: identity
            with ui.column().classes("gap-0"):
                ui.label(eleve["eleve_id"]).classes("text-h6")

            # Right: metrics
            with ui.row().classes("gap-4"):
                absences = eleve.get("absences_demi_journees", 0) or 0
                if absences > 10:
                    metric_card("Absences", absences, delta="Elevees", inverse=True)
                else:
                    metric_card("Absences", absences)

                retards = eleve.get("retards", 0) or 0
                metric_card("Retards", retards)

        # Subject count
        nb_matieres = eleve.get("nb_matieres", 0)
        if nb_matieres:
            ui.label(f"{nb_matieres} matieres").classes("text-caption text-grey-7")

        # Synthesis status badge
        if synthese:
            status = synthese.get("status", "unknown")
            _status_chip(status)
        else:
            ui.label("Pas de synthese").classes("text-caption text-grey-6")


def eleve_detail_header(eleve: dict) -> None:
    """Render detailed student header with all metrics.

    Args:
        eleve: Full student data with matieres.
    """
    ui.label(eleve["eleve_id"]).classes("text-h5")

    with ui.row().classes("gap-4 q-mt-sm"):
        metric_card("Classe", eleve.get("classe", "N/A"))
        metric_card("Absences", eleve.get("absences_demi_journees", 0) or 0)
        metric_card("Retards", eleve.get("retards", 0) or 0)

    # Engagements, parcours, evenements
    for field, label in [
        ("engagements", "Engagements"),
        ("parcours", "Parcours"),
        ("evenements", "Evenements"),
    ]:
        items = eleve.get(field, [])
        if items:
            ui.label(f"{label} : {', '.join(items)}").classes("text-body2")

    ui.separator()

    # Subjects
    matieres = eleve.get("matieres", [])
    if matieres:
        ui.label("Matieres").classes("text-h6 q-mt-sm")
        for matiere in matieres:
            with ui.expansion(
                f"{matiere['nom']} - {matiere.get('moyenne_eleve', 'N/A')}/20"
            ).classes("w-full"):
                with ui.row().classes("w-full gap-8"):
                    with ui.column():
                        ui.label(
                            f"Professeur : {matiere.get('professeur', 'N/A')}"
                        ).classes("text-caption")
                        ui.label(
                            f"Moyenne classe : {matiere.get('moyenne_classe', 'N/A')}"
                        ).classes("text-caption")
                    appreciation = matiere.get("appreciation", "")
                    if appreciation:
                        ui.label(appreciation).classes("text-body2 italic")


def _status_chip(status: str) -> None:
    """Render a colored status chip."""
    color_map = {
        "validated": "positive",
        "edited": "info",
        "generated": "warning",
    }
    label_map = {
        "validated": "Synthese validee",
        "edited": "Synthese modifiee",
        "generated": "Synthese generee (a valider)",
    }
    color = color_map.get(status, "grey")
    text = label_map.get(status, f"Status: {status}")
    ui.badge(text, color=color)
