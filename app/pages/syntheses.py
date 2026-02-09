"""Page Synthèses — Stub Phase 1."""

from layout import page_layout
from nicegui import ui
from state import get_classe_id, get_trimestre


@ui.page("/syntheses")
def syntheses_page():
    with page_layout("Synthèses"):
        classe_id = get_classe_id()
        trimestre = get_trimestre()

        if not classe_id:
            ui.label("Sélectionnez une classe dans la barre latérale.").classes(
                "text-grey-6"
            )
            return

        ui.label(f"Classe : {classe_id}").classes("text-body1")
        ui.label(f"Trimestre : T{trimestre}").classes("text-body1")
        ui.label(
            "Génération et édition des synthèses — à implémenter en Phase 3."
        ).classes("text-grey-6 q-mt-md")
