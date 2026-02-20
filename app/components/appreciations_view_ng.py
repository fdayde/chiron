"""Appreciations view component — NiceGUI version."""

from __future__ import annotations

from nicegui import ui


def eleve_header(eleve: dict) -> None:
    """Render compact student header with key metrics on one line.

    Args:
        eleve: Student data dict.
    """
    absences = eleve.get("absences_demi_journees", 0) or 0
    retards = eleve.get("retards", 0) or 0
    matieres = eleve.get("matieres", [])
    nb_matieres = len(matieres)

    # Calculate average
    moy_eleve = _calc_moyenne_eleve(matieres)

    with ui.row().classes("items-center gap-2 flex-wrap"):
        ui.label(
            f"{absences} abs. · {retards} retard{'s' if retards != 1 else ''}"
            f" · {nb_matieres} matière{'s' if nb_matieres != 1 else ''}"
        ).classes("text-body2 text-grey-5")

        if moy_eleve is not None:
            ui.label(f"Moy. élève : {moy_eleve:.1f}/20").classes(
                "text-body2 text-weight-bold"
            )


def _calc_moyenne_eleve(matieres: list[dict]) -> float | None:
    """Calculate student average across all subjects."""
    notes = [m["moyenne_eleve"] for m in matieres if m.get("moyenne_eleve") is not None]
    return sum(notes) / len(notes) if notes else None


def appreciations(
    eleve: dict,
    editable: bool = False,
    on_save: callable | None = None,
) -> None:
    """Render subject appreciations in a compact format.

    Designed for side-by-side layout with synthesis.

    Args:
        eleve: Full student data with matieres.
        editable: If True, appreciations are shown as editable textareas.
        on_save: Callback called with updated matieres list on save.
    """
    matieres = eleve.get("matieres", [])

    if not matieres:
        ui.label("Aucune matière disponible.").classes("text-grey-6")
        return

    # Keep references to textareas for collecting edited values
    textarea_refs: list[tuple[int, ui.textarea]] = []

    for idx, matiere in enumerate(matieres):
        with ui.card().classes("w-full q-mb-xs").style("padding: 8px 12px"):
            with ui.row().classes("w-full items-center justify-between"):
                # Left: subject + teacher
                with ui.column().classes("gap-0"):
                    ui.label(matiere["nom"]).classes("text-weight-bold text-body2")
                    prof = matiere.get("professeur", "")
                    if prof:
                        ui.label(prof).classes("text-caption text-grey-7")

                # Right: grade
                note = matiere.get("moyenne_eleve")
                if note is not None:
                    ui.label(f"{note}/20").classes("text-weight-bold text-body2")

            # Appreciation text
            appreciation = matiere.get("appreciation", "")
            if editable:
                ta = (
                    ui.textarea(value=appreciation)
                    .props("rows=2 dense")
                    .classes("w-full text-body2 q-mt-xs")
                )
                textarea_refs.append((idx, ta))
            elif appreciation:
                ui.label(appreciation).classes("text-body2 italic q-mt-xs")

    if editable and on_save and textarea_refs:

        def _do_save():
            updated_matieres = []
            for m in matieres:
                updated_matieres.append(dict(m))
            for idx, ta in textarea_refs:
                updated_matieres[idx]["appreciation"] = ta.value
            on_save(updated_matieres)

        ui.button(
            "Sauvegarder les modifications",
            icon="save",
            on_click=_do_save,
        ).props("color=primary rounded dense").classes("q-mt-sm")


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
        ui.label("Aucune appréciation disponible.").classes("text-caption text-grey-6")
        return

    for matiere in with_appreciation[:max_display]:
        note = matiere.get("moyenne_eleve", "-")
        ui.label(f"{matiere['nom']} ({note}/20)").classes("text-weight-bold text-body2")
        ui.label(matiere.get("appreciation", "")).classes("text-caption text-grey-7")
        ui.separator()

    remaining = len(with_appreciation) - max_display
    if remaining > 0:
        ui.label(f"... et {remaining} autre(s) matière(s)").classes(
            "text-caption text-grey-6"
        )
