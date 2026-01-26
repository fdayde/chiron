"""Synthesis editor component."""

from __future__ import annotations

import streamlit as st

from app.api_client import ChironAPIClient
from app.config import ui_settings


def get_llm_settings() -> tuple[str, str | None, float]:
    """Get LLM settings from session state or defaults.

    Returns:
        Tuple of (provider, model, temperature).
    """
    provider = st.session_state.get("llm_provider", ui_settings.default_provider)
    model = st.session_state.get("llm_model", ui_settings.default_model) or None
    temperature = st.session_state.get(
        "llm_temperature", ui_settings.default_temperature
    )
    return provider, model, temperature


def render_synthese_editor(
    client: ChironAPIClient,
    eleve_id: str,
    synthese: dict | None,
    synthese_id: str | None = None,
    trimestre: int = 1,
) -> None:
    """Render synthesis editor.

    Args:
        client: API client
        eleve_id: Student ID
        synthese: Current synthesis data or None
        synthese_id: Synthesis ID for updates
        trimestre: Current trimester
    """
    st.markdown("### Synthese")

    if not synthese:
        st.info("Aucune synthese generee pour cet eleve.")

        if st.button(
            "Generer la synthese",
            key=f"gen_{eleve_id}",
            type="primary",
        ):
            provider, model, temperature = get_llm_settings()
            with st.spinner(f"Generation en cours via {provider}..."):
                try:
                    result = client.generate_synthese(
                        eleve_id,
                        trimestre,
                        provider=provider,
                        model=model,
                        temperature=temperature,
                    )
                    # Show metadata
                    meta = result.get("metadata", {})
                    st.success(
                        f"Synthese generee en {meta.get('duration_ms', 0)}ms "
                        f"({meta.get('tokens_total', 'N/A')} tokens)"
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur de generation: {e}")
        return

    # Display synthesis
    synthese_texte = synthese.get("synthese_texte", "")

    # Editable text
    new_text = st.text_area(
        "Texte de la synthese",
        value=synthese_texte,
        height=200,
        key=f"synthese_text_{eleve_id}",
    )

    # Insights
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Alertes")
        alertes = synthese.get("alertes", [])
        if alertes:
            for alerte in alertes:
                with st.container(border=True):
                    st.markdown(f"**{alerte.get('matiere', 'N/A')}**")
                    st.caption(alerte.get("description", ""))
        else:
            st.caption("Aucune alerte")

    with col2:
        st.markdown("#### Reussites")
        reussites = synthese.get("reussites", [])
        if reussites:
            for reussite in reussites:
                with st.container(border=True):
                    st.markdown(f"**{reussite.get('matiere', 'N/A')}**")
                    st.caption(reussite.get("description", ""))
        else:
            st.caption("Aucune reussite")

    # Posture
    posture = synthese.get("posture_generale", "N/A")
    st.markdown(f"**Posture generale:** {posture}")

    # Axes de travail
    axes = synthese.get("axes_travail", [])
    if axes:
        st.markdown("**Axes de travail:** " + ", ".join(axes))

    st.divider()

    # Actions
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button(
            "Sauvegarder",
            key=f"save_{eleve_id}",
            disabled=new_text == synthese_texte,
        ):
            if synthese_id:
                try:
                    client.update_synthese(synthese_id, synthese_texte=new_text)
                    st.success("Synthese sauvegardee!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur: {e}")

    with col2:
        if st.button(
            "Valider",
            key=f"validate_{eleve_id}",
            type="primary",
        ):
            if synthese_id:
                try:
                    client.validate_synthese(synthese_id)
                    st.success("Synthese validee!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur: {e}")

    with col3:
        if st.button(
            "Regenerer",
            key=f"regen_{eleve_id}",
        ):
            provider, model, temperature = get_llm_settings()
            with st.spinner(f"Regeneration en cours via {provider}..."):
                try:
                    # Delete old and generate new
                    if synthese_id:
                        client.delete_synthese(synthese_id)
                    result = client.generate_synthese(
                        eleve_id,
                        trimestre,
                        provider=provider,
                        model=model,
                        temperature=temperature,
                    )
                    meta = result.get("metadata", {})
                    st.success(
                        f"Synthese regeneree en {meta.get('duration_ms', 0)}ms "
                        f"({meta.get('tokens_total', 'N/A')} tokens)"
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur: {e}")
