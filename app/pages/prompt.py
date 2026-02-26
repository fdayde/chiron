"""Page Prompt — Affiche le prompt de génération."""

import json

from cache import fetch_fewshot_count
from layout import page_layout
from nicegui import ui
from state import get_classe_id, get_trimestre

from src.core.constants import CUSTOM_SYSTEM_PROMPT_PATH
from src.generation.prompts import (
    CURRENT_PROMPT,
    get_prompt,
    get_prompt_hash,
    is_prompt_customized,
    reset_system_prompt,
)


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

        # --- Message flow diagram ---
        with ui.row().classes("items-center gap-2"):
            ui.icon("forum").classes("text-primary")
            ui.label("Structure des messages envoyés au LLM").classes("text-h6")

        # Few-shot count
        classe_id = get_classe_id()
        trimestre = get_trimestre()
        fewshot_count = 0
        if classe_id:
            fewshot_count = fetch_fewshot_count(classe_id, trimestre)

        flow_lines = [
            "1.  [system]     System prompt (instructions ci-dessous)",
        ]
        if fewshot_count > 0:
            for i in range(fewshot_count):
                n = i + 1
                flow_lines.append(
                    f"{len(flow_lines) + 1}.  [user]       Few-shot exemple {n} — données élève"
                )
                flow_lines.append(
                    f"{len(flow_lines) + 1}.  [assistant]  Few-shot exemple {n} — synthèse validée"
                )
        flow_lines.append(
            f"{len(flow_lines) + 1}.  [user]       Élève cible — données du bulletin"
        )

        with (
            ui.card()
            .classes("w-full q-mt-sm p-3")
            .style("border-left: 3px solid var(--q-primary)")
        ):
            for line in flow_lines:
                ui.label(line).classes("text-body2").style("font-family: monospace;")
            if fewshot_count > 0:
                ui.label(f"{fewshot_count} exemple(s) de calibration actif(s)").classes(
                    "text-caption text-green q-mt-xs"
                )
            else:
                ui.label(
                    "Aucun exemple few-shot — cochez « Utiliser comme exemple » "
                    "sur des synthèses validées pour calibrer le style."
                ).classes("text-caption text-orange q-mt-xs")

        ui.separator().classes("q-my-md")

        # System prompt
        with ui.row().classes("items-center gap-2"):
            ui.icon("settings").classes("text-primary")
            ui.label("System prompt").classes("text-h6")
            ui.button(
                icon="content_copy",
                on_click=lambda: ui.run_javascript(
                    f"navigator.clipboard.writeText({json.dumps(template['system'])})"
                    ".then(() => null)"
                ),
            ).props("flat dense size=sm").tooltip("Copier le system prompt")

        # Customization notice
        with (
            ui.card()
            .classes("w-full q-mt-sm p-3")
            .style("border-left: 3px solid var(--q-primary)")
        ):
            ui.label(
                "Vous pouvez personnaliser ce prompt en éditant le fichier "
                "ci-dessous avec un éditeur de texte. "
                "Rechargez cette page (F5) après modification pour voir les changements. "
                "Les modifications seront prises en compte à la prochaine génération."
            ).classes("text-body2")
            customized = is_prompt_customized()
            with ui.row().classes("items-center gap-2 q-mt-xs"):
                ui.label(f"{CUSTOM_SYSTEM_PROMPT_PATH}").classes(
                    "text-caption text-grey-6"
                ).style("font-family: monospace;")
                if customized:
                    ui.badge("Modifié", color="orange").props("outline")

                    def do_reset():
                        reset_system_prompt()
                        ui.notify(
                            "Prompt réinitialisé. Rechargez la page.",
                            type="positive",
                        )

                    ui.button(
                        "Réinitialiser",
                        icon="restart_alt",
                        on_click=do_reset,
                    ).props("flat dense size=sm color=orange").tooltip(
                        "Revenir au prompt par défaut"
                    )
        ui.code(template["system"]).classes("w-full q-mt-sm")

        ui.separator().classes("q-my-md")

        # User template
        with ui.row().classes("items-center gap-2"):
            ui.icon("person").classes("text-primary")
            ui.label("User prompt (template)").classes("text-h6")
            ui.button(
                icon="content_copy",
                on_click=lambda: ui.run_javascript(
                    f"navigator.clipboard.writeText({json.dumps(template['user'])})"
                    ".then(() => null)"
                ),
            ).props("flat dense size=sm").tooltip("Copier le user template")
        ui.label(
            "Message envoyé pour chaque élève. "
            "{eleve_data} est remplacé par les données du bulletin."
        ).classes("text-caption text-grey-6")
        ui.code(template["user"]).classes("w-full q-mt-sm")
