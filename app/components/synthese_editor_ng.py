"""Synthesis editor component — NiceGUI version."""

from __future__ import annotations

import json

from cache import (
    clear_eleves_cache,
    delete_synthese_direct,
    generate_synthese_direct,
    update_synthese_direct,
    validate_synthese_direct,
)
from nicegui import run, ui


def _build_insights_text(synthese: dict) -> str:
    """Build a plain-text version of all insights for copy-paste.

    Args:
        synthese: Synthesis data dict.

    Returns:
        Formatted plain text.
    """
    parts: list[str] = []

    alertes = synthese.get("alertes", [])
    if alertes:
        parts.append("ALERTES :")
        for a in alertes:
            parts.append(f"  - {a.get('matiere', '?')} : {a.get('description', '')}")

    reussites = synthese.get("reussites", [])
    if reussites:
        if parts:
            parts.append("")
        parts.append("RÉUSSITES :")
        for r in reussites:
            parts.append(f"  - {r.get('matiere', '?')} : {r.get('description', '')}")

    axes = synthese.get("axes_travail", [])
    if axes:
        if parts:
            parts.append("")
        parts.append("CONSEILS & PISTES DE PROGRESSION :")
        for axe in axes:
            parts.append(f"  - {axe}")

    biais = synthese.get("biais_detectes", [])
    if biais:
        if parts:
            parts.append("")
        parts.append("BIAIS DE GENRE DÉTECTÉS :")
        for b in biais:
            parts.append(
                f'  - {b.get("matiere", "?")} : "{b.get("formulation_biaisee", "")}" '
                f"→ {b.get('suggestion', '')}"
            )

    return "\n".join(parts)


def _render_insights_panel(synthese: dict) -> None:
    """Render the insights panel with selectable text and copy button.

    Args:
        synthese: Synthesis data dict.
    """
    insights_text = _build_insights_text(synthese)
    if not insights_text:
        return

    with (
        ui.card()
        .classes("w-full q-mt-sm p-3")
        .style("user-select: text; cursor: text;")
    ):
        with ui.row().classes("w-full items-center justify-between q-mb-xs"):
            ui.label("Analyse").classes("text-weight-bold text-body2")
            ui.button(
                icon="content_copy",
                on_click=lambda: ui.run_javascript(
                    f"navigator.clipboard.writeText({json.dumps(insights_text)})"
                    ".then(() => null)"
                ),
            ).props("flat dense size=sm").tooltip("Copier l'analyse")

        # Alertes
        alertes = synthese.get("alertes", [])
        if alertes:
            with ui.row().classes("items-center gap-1 q-mb-xs"):
                ui.icon("warning", size="xs").classes("text-orange")
                ui.label("Signaux d'attention").classes("text-weight-bold text-caption")
            for alerte in alertes:
                ui.label(
                    f"  {alerte.get('matiere', '?')} : {alerte.get('description', '')}"
                ).classes("text-caption text-orange").style("user-select: text;")

        # Reussites
        reussites = synthese.get("reussites", [])
        if reussites:
            with ui.row().classes("items-center gap-1 q-mt-xs q-mb-xs"):
                ui.icon("emoji_events", size="xs").classes("text-green")
                ui.label("Réussites").classes("text-weight-bold text-caption")
            for reussite in reussites:
                ui.label(
                    f"  {reussite.get('matiere', '?')} : {reussite.get('description', '')}"
                ).classes("text-caption text-green").style("user-select: text;")

        # Conseils & pistes de progression
        axes = synthese.get("axes_travail", [])
        if axes:
            with ui.row().classes("items-center gap-1 q-mt-xs q-mb-xs"):
                ui.icon("psychology", size="xs").classes("text-blue")
                ui.label("Conseils & pistes de progression").classes(
                    "text-weight-bold text-caption"
                )
            for axe in axes:
                ui.label(f"  • {axe}").classes("text-caption").style(
                    "user-select: text;"
                )

        # Biais
        biais = synthese.get("biais_detectes", [])
        if biais:
            with ui.row().classes("items-center gap-1 q-mt-xs q-mb-xs"):
                ui.icon("balance", size="xs").classes("text-purple")
                ui.label("Biais de genre").classes("text-weight-bold text-caption")
            for b in biais:
                ui.label(
                    f'  {b.get("matiere", "?")} : "{b.get("formulation_biaisee", "")}" '
                    f"→ {b.get('suggestion', '')}"
                ).classes("text-caption text-purple").style("user-select: text;")


def synthese_display(synthese: dict) -> None:
    """Render synthesis content (read-only display).

    Args:
        synthese: Synthesis data dict.
    """
    synthese_texte = synthese.get("synthese_texte", "")
    ui.markdown(synthese_texte)

    ui.separator()

    _render_insights_panel(synthese)


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
        ui.label("Aucune synthèse générée pour cet élève.").classes(
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
                ui.notify(f"Générée ({tokens} tokens, ${cost:.4f})", type="positive")
                clear_eleves_cache()
                if on_action:
                    on_action()
            except Exception as e:
                ui.notify(f"Erreur: {e}", type="negative")
            finally:
                gen_btn.props(remove="loading")

        gen_btn = ui.button("Générer", icon="auto_awesome", on_click=_generate).props(
            "color=primary rounded"
        )
        return

    # Editable text area
    synthese_texte = synthese.get("synthese_texte", "")
    ui.label("Vous pouvez modifier le texte avant de valider.").classes(
        "text-caption text-grey-7 q-mb-xs"
    )
    text_area = (
        ui.textarea(
            label="Texte de la synthèse",
            value=synthese_texte,
        )
        .classes("w-full")
        .props("rows=8")
        .style("line-height: 1.8")
    )

    # Modification indicator
    modified_label = ui.label("Modifié").classes(
        "text-caption text-orange q-mt-xs hidden"
    )

    def _on_text_change(e):
        if e.value != synthese_texte:
            modified_label.set_visibility(True)
        else:
            modified_label.set_visibility(False)

    text_area.on_value_change(_on_text_change)

    # Analyse panel (selectable + copiable)
    _render_insights_panel(synthese)

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
                ui.notify("Validée", type="positive")
                clear_eleves_cache()
                if on_action:
                    on_action()
            except Exception as e:
                ui.notify(f"Erreur: {e}", type="negative")
            finally:
                validate_btn.props(remove="loading")

        validate_btn = ui.button("Valider", icon="check", on_click=_validate).props(
            "color=primary rounded"
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
                ui.notify(f"Régénérée ({tokens} tokens)", type="positive")
                clear_eleves_cache()
                if on_action:
                    on_action()
            except Exception as e:
                ui.notify(f"Erreur: {e}", type="negative")
            finally:
                regen_btn.props(remove="loading")

        regen_btn = ui.button("Régénérer", icon="refresh", on_click=_regenerate).props(
            "outline color=orange rounded"
        )
