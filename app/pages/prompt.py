"""Page Prompt — Affiche le prompt de génération."""

from layout import page_layout
from nicegui import ui

from src.generation.prompts import CURRENT_PROMPT, get_prompt, get_prompt_hash


@ui.page("/prompt")
def prompt_page():
    with page_layout("Prompt de génération"):
        template = get_prompt(CURRENT_PROMPT)
        prompt_hash = get_prompt_hash(CURRENT_PROMPT)

        # Metadata
        with ui.row().classes("gap-4 q-mt-md"):
            with ui.card().classes("p-4"):
                ui.label("Template").classes("text-caption text-grey-7")
                ui.label(CURRENT_PROMPT).classes("text-h6")
            with ui.card().classes("p-4"):
                ui.label("Version").classes("text-caption text-grey-7")
                ui.label(template["version"]).classes("text-h6")
            with ui.card().classes("p-4"):
                ui.label("Hash").classes("text-caption text-grey-7")
                ui.label(prompt_hash).classes("text-h6")

        ui.label(template.get("description", "")).classes(
            "text-caption text-grey-6 q-mt-sm"
        )

        ui.separator().classes("q-my-md")

        # System prompt
        with ui.row().classes("items-center gap-2"):
            ui.icon("settings").classes("text-primary")
            ui.label("System prompt").classes("text-h6")
        ui.label("Instructions envoyées au LLM avant les données de l'élève.").classes(
            "text-caption text-grey-6"
        )
        ui.code(template["system"]).classes("w-full q-mt-sm")

        ui.separator().classes("q-my-md")

        # User template
        with ui.row().classes("items-center gap-2"):
            ui.icon("person").classes("text-primary")
            ui.label("User prompt (template)").classes("text-h6")
        ui.label(
            "Message envoyé pour chaque élève. "
            "{eleve_data} est remplacé par les données du bulletin."
        ).classes("text-caption text-grey-6")
        ui.code(template["user"]).classes("w-full q-mt-sm")
