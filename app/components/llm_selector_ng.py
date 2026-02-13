"""LLM provider/model selector component — NiceGUI version."""

from __future__ import annotations

from config_ng import (
    LLM_PROVIDERS,
    estimate_total_cost,
    format_model_label,
    ui_settings,
)
from nicegui import ui


def llm_selector(on_change: callable | None = None) -> tuple[ui.select, ui.select]:
    """Render LLM provider and model selectors.

    Args:
        on_change: Optional callback called with (provider, model) on any change.

    Returns:
        Tuple of (provider_select, model_select) NiceGUI elements.
    """
    provider_keys = list(LLM_PROVIDERS.keys())
    provider_options = {k: LLM_PROVIDERS[k]["name"] for k in provider_keys}
    default_provider = ui_settings.default_provider
    if default_provider not in provider_options:
        default_provider = provider_keys[0]

    default_model = LLM_PROVIDERS[default_provider].get("default", "")
    model_options = {
        m: format_model_label(default_provider, m)
        for m in LLM_PROVIDERS[default_provider]["models"]
    }

    with ui.row().classes("gap-4 items-end"):
        provider_select = ui.select(
            options=provider_options,
            label="Provider",
            value=default_provider,
        ).classes("w-48")

        model_select = ui.select(
            options=model_options,
            label="Modèle",
            value=default_model if default_model in model_options else None,
        ).classes("w-64")

    def _on_provider_change(e):
        prov = e.value
        models = LLM_PROVIDERS[prov]["models"]
        new_options = {m: format_model_label(prov, m) for m in models}
        model_select.options = new_options
        new_default = LLM_PROVIDERS[prov].get("default", "")
        model_select.value = (
            new_default
            if new_default in new_options
            else (models[0] if models else None)
        )
        model_select.update()
        if on_change:
            on_change(prov, model_select.value)

    def _on_model_change(e):
        if on_change:
            on_change(provider_select.value, e.value)

    provider_select.on_value_change(_on_provider_change)
    model_select.on_value_change(_on_model_change)

    return provider_select, model_select


def cost_estimate_label(provider: str, model: str, nb_eleves: int) -> ui.label | None:
    """Display cost estimate for generation.

    Args:
        provider: LLM provider.
        model: Model name.
        nb_eleves: Number of students.

    Returns:
        The label element, or None if nb_eleves <= 0.
    """
    if nb_eleves <= 0:
        return None

    cost = estimate_total_cost(provider, model, nb_eleves)
    return ui.label(f"Coût estimé : ~${cost:.4f} pour {nb_eleves} élève(s)").classes(
        "text-caption text-grey-7"
    )
