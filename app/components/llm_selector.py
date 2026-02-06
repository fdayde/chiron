"""LLM provider/model selector component."""

from __future__ import annotations

import streamlit as st
from config import LLM_PROVIDERS, estimate_total_cost, format_model_label, ui_settings


def render_llm_selector(key_prefix: str = "llm") -> tuple[str, str]:
    """Render LLM provider and model selectors.

    Args:
        key_prefix: Prefix for session state keys to avoid conflicts.

    Returns:
        Tuple of (provider, model).
    """
    col1, col2 = st.columns(2)

    provider_keys = list(LLM_PROVIDERS.keys())
    default_provider = ui_settings.default_provider
    provider_index = (
        provider_keys.index(default_provider)
        if default_provider in provider_keys
        else 0
    )

    with col1:
        provider = st.selectbox(
            "Provider",
            options=provider_keys,
            index=provider_index,
            format_func=lambda x: LLM_PROVIDERS[x]["name"],
            key=f"{key_prefix}_provider",
        )

    with col2:
        models = LLM_PROVIDERS[provider]["models"]
        # Sélectionner le modèle par défaut du provider
        default_model = LLM_PROVIDERS[provider].get("default", "")
        model_index = models.index(default_model) if default_model in models else 0
        model = st.selectbox(
            "Modèle",
            options=models,
            index=model_index,
            format_func=lambda x: format_model_label(provider, x),
            key=f"{key_prefix}_model",
        )

    return provider, model


def render_cost_estimate(provider: str, model: str, nb_eleves: int) -> None:
    """Display cost estimate for generation.

    Args:
        provider: LLM provider.
        model: Model name.
        nb_eleves: Number of students.
    """
    if nb_eleves <= 0:
        return

    cost = estimate_total_cost(provider, model, nb_eleves)
    st.caption(f"💰 Coût estimé : **~${cost:.4f}** pour {nb_eleves} élève(s)")
