"""Synthesis editor component — NiceGUI version."""

from __future__ import annotations

from cache import (
    clear_eleves_cache,
    delete_synthese_direct,
    generate_synthese_direct,
    update_synthese_direct,
    validate_synthese_direct,
)
from nicegui import run, ui


def synthese_display(synthese: dict) -> None:
    """Render synthesis content (read-only display).

    Args:
        synthese: Synthesis data dict.
    """
    synthese_texte = synthese.get("synthese_texte", "")
    ui.markdown(synthese_texte)

    ui.separator()

    with ui.row().classes("w-full gap-8"):
        # Alertes
        with ui.column().classes("flex-1"):
            ui.label("Alertes").classes("text-weight-bold")
            alertes = synthese.get("alertes", [])
            if alertes:
                for alerte in alertes:
                    with ui.card().classes("w-full p-2 q-mb-xs"):
                        ui.label(alerte.get("matiere", "N/A")).classes(
                            "text-weight-bold text-body2"
                        )
                        ui.label(alerte.get("description", "")).classes("text-caption")
            else:
                ui.label("Aucune alerte").classes("text-caption text-grey-6")

        # Reussites
        with ui.column().classes("flex-1"):
            ui.label("Reussites").classes("text-weight-bold")
            reussites = synthese.get("reussites", [])
            if reussites:
                for reussite in reussites:
                    with ui.card().classes("w-full p-2 q-mb-xs"):
                        ui.label(reussite.get("matiere", "N/A")).classes(
                            "text-weight-bold text-body2"
                        )
                        ui.label(reussite.get("description", "")).classes(
                            "text-caption"
                        )
            else:
                ui.label("Aucune reussite").classes("text-caption text-grey-6")

    # Posture and axes
    posture = synthese.get("posture_generale")
    if posture:
        ui.label(f"Posture generale : {posture}").classes("text-body2 q-mt-sm")

    axes = synthese.get("axes_travail", [])
    if axes:
        ui.label(f"Axes de travail : {', '.join(axes)}").classes("text-body2")


def synthese_editor(
    eleve_id: str,
    synthese: dict | None,
    synthese_id: str | None,
    trimestre: int,
    provider: str,
    model: str,
    on_action: callable | None = None,
) -> None:
    """Render synthesis editor with generate/save/validate/regenerate actions.

    Args:
        eleve_id: Student ID.
        synthese: Current synthesis data or None.
        synthese_id: Synthesis ID for updates.
        trimestre: Current trimester.
        provider: LLM provider for generation.
        model: LLM model for generation.
        on_action: Callback invoked after any successful action (for refresh).
    """
    if not synthese:
        ui.label("Aucune synthese generee pour cet eleve.").classes(
            "text-grey-6 q-mb-sm"
        )

        async def _generate():
            gen_btn.props(add="loading")
            try:
                result = await run.io_bound(
                    generate_synthese_direct,
                    eleve_id,
                    trimestre,
                    provider=provider,
                    model=model,
                )
                meta = result.get("metadata", {})
                tokens = meta.get("tokens_total", "?")
                cost = meta.get("cost_usd", 0)
                ui.notify(f"Generee ({tokens} tokens, ${cost:.4f})", type="positive")
                clear_eleves_cache()
                if on_action:
                    on_action()
            except Exception as e:
                ui.notify(f"Erreur: {e}", type="negative")
            finally:
                gen_btn.props(remove="loading")

        gen_btn = ui.button("Generer", icon="auto_awesome", on_click=_generate).props(
            "color=primary"
        )
        return

    # Editable text area
    synthese_texte = synthese.get("synthese_texte", "")
    ui.label("Vous pouvez modifier le texte avant de valider.").classes(
        "text-caption text-grey-7 q-mb-xs"
    )
    text_area = (
        ui.textarea(
            label="Texte de la synthese",
            value=synthese_texte,
        )
        .classes("w-full")
        .props("rows=8")
    )

    # Insights: alertes + reussites
    with ui.row().classes("w-full gap-8 q-mt-sm"):
        with ui.column().classes("flex-1"):
            ui.label("Alertes").classes("text-weight-bold")
            alertes = synthese.get("alertes", [])
            if alertes:
                for alerte in alertes:
                    ui.label(
                        f"- {alerte.get('matiere', '?')}: {alerte.get('description', '')}"
                    ).classes("text-caption")
            else:
                ui.label("Aucune").classes("text-caption text-grey-6")

        with ui.column().classes("flex-1"):
            ui.label("Reussites").classes("text-weight-bold")
            reussites = synthese.get("reussites", [])
            if reussites:
                for reussite in reussites:
                    ui.label(
                        f"- {reussite.get('matiere', '?')}: {reussite.get('description', '')}"
                    ).classes("text-caption")
            else:
                ui.label("Aucune").classes("text-caption text-grey-6")

    # Posture and axes (compact)
    posture = synthese.get("posture_generale")
    axes = synthese.get("axes_travail", [])
    if posture or axes:
        parts = []
        if posture:
            parts.append(f"Posture: {posture}")
        if axes:
            parts.append(f"Axes: {', '.join(axes)}")
        ui.label(" | ".join(parts)).classes("text-caption text-grey-7 q-mt-xs")

    ui.separator().classes("q-my-sm")

    # Action buttons
    with ui.row().classes("gap-2"):
        # Validate (saves text + marks as validated)
        async def _validate():
            if not synthese_id:
                return
            validate_btn.props(add="loading")
            try:
                new_text = text_area.value
                if new_text != synthese_texte:
                    await run.io_bound(update_synthese_direct, synthese_id, new_text)
                await run.io_bound(validate_synthese_direct, synthese_id)
                ui.notify("Validee", type="positive")
                clear_eleves_cache()
                if on_action:
                    on_action()
            except Exception as e:
                ui.notify(f"Erreur: {e}", type="negative")
            finally:
                validate_btn.props(remove="loading")

        validate_btn = ui.button("Valider", icon="check", on_click=_validate).props(
            "color=primary"
        )

        # Regenerate
        async def _regenerate():
            regen_btn.props(add="loading")
            try:
                if synthese_id:
                    await run.io_bound(delete_synthese_direct, synthese_id)
                result = await run.io_bound(
                    generate_synthese_direct,
                    eleve_id,
                    trimestre,
                    provider=provider,
                    model=model,
                )
                meta = result.get("metadata", {})
                tokens = meta.get("tokens_total", "?")
                ui.notify(f"Regeneree ({tokens} tokens)", type="positive")
                clear_eleves_cache()
                if on_action:
                    on_action()
            except Exception as e:
                ui.notify(f"Erreur: {e}", type="negative")
            finally:
                regen_btn.props(remove="loading")

        regen_btn = ui.button("Regenerer", icon="refresh", on_click=_regenerate).props(
            "outline color=orange"
        )
