"""Page Prompt — Affiche le prompt de génération."""

from cache import fetch_fewshot_count
from layout import page_layout
from nicegui import ui
from state import get_classe_id, get_trimestre

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

        # --- Message flow diagram ---
        with ui.row().classes("items-center gap-2"):
            ui.icon("forum").classes("text-primary")
            ui.label("Structure des messages envoyes au LLM").classes("text-h6")

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
                    f"{len(flow_lines) + 1}.  [user]       Few-shot exemple {n} — donnees eleve"
                )
                flow_lines.append(
                    f"{len(flow_lines) + 1}.  [assistant]  Few-shot exemple {n} — synthese validee"
                )
        flow_lines.append(
            f"{len(flow_lines) + 1}.  [user]       Eleve cible — donnees du bulletin"
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
                    "sur des syntheses validees pour calibrer le style."
                ).classes("text-caption text-orange q-mt-xs")

        ui.separator().classes("q-my-md")

        # System prompt
        with ui.row().classes("items-center gap-2"):
            ui.icon("settings").classes("text-primary")
            ui.label("System prompt").classes("text-h6")
        ui.label("Instructions envoyees au LLM avant les donnees de l'eleve.").classes(
            "text-caption text-grey-6"
        )
        ui.code(template["system"]).classes("w-full q-mt-sm")

        ui.separator().classes("q-my-md")

        # User template
        with ui.row().classes("items-center gap-2"):
            ui.icon("person").classes("text-primary")
            ui.label("User prompt (template)").classes("text-h6")
        ui.label(
            "Message envoye pour chaque eleve. "
            "{eleve_data} est remplace par les donnees du bulletin."
        ).classes("text-caption text-grey-6")
        ui.code(template["user"]).classes("w-full q-mt-sm")
