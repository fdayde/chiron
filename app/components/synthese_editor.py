"""Synthesis editor component."""

from __future__ import annotations

import streamlit as st
from api_client import ChironAPIClient
from components.data_helpers import clear_eleves_cache


def render_synthese_display(synthese: dict) -> None:
    """Render synthesis content (read-only display).

    Args:
        synthese: Synthesis data dict.
    """
    # Main text
    synthese_texte = synthese.get("synthese_texte", "")
    st.markdown(synthese_texte)

    st.divider()

    # Insights in two columns
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Alertes**")
        alertes = synthese.get("alertes", [])
        if alertes:
            for alerte in alertes:
                with st.container(border=True):
                    st.markdown(f"**{alerte.get('matiere', 'N/A')}**")
                    st.caption(alerte.get("description", ""))
        else:
            st.caption("Aucune alerte")

    with col2:
        st.markdown("**Réussites**")
        reussites = synthese.get("reussites", [])
        if reussites:
            for reussite in reussites:
                with st.container(border=True):
                    st.markdown(f"**{reussite.get('matiere', 'N/A')}**")
                    st.caption(reussite.get("description", ""))
        else:
            st.caption("Aucune réussite")

    # Posture and axes
    posture = synthese.get("posture_generale")
    if posture:
        st.markdown(f"**Posture générale:** {posture}")

    axes = synthese.get("axes_travail", [])
    if axes:
        st.markdown(f"**Axes de travail:** {', '.join(axes)}")


def render_synthese_editor(
    client: ChironAPIClient,
    eleve_id: str,
    synthese: dict | None,
    synthese_id: str | None,
    trimestre: int,
    provider: str,
    model: str,
) -> bool:
    """Render synthesis editor with actions.

    Args:
        client: API client.
        eleve_id: Student ID.
        synthese: Current synthesis data or None.
        synthese_id: Synthesis ID for updates.
        trimestre: Current trimester.
        provider: LLM provider for generation/regeneration.
        model: LLM model for generation/regeneration.

    Returns:
        True if an action was performed that requires refresh.
    """
    action_performed = False

    if not synthese:
        st.info("Aucune synthèse générée pour cet élève.")

        if st.button("Générer", key=f"gen_{eleve_id}", type="primary"):
            with st.spinner(f"Génération via {provider}..."):
                try:
                    result = client.generate_synthese(
                        eleve_id, trimestre, provider=provider, model=model
                    )
                    meta = result.get("metadata", {})
                    tokens = meta.get("tokens_total", "?")
                    cost = meta.get("cost_usd", 0)
                    st.success(f"Générée ({tokens} tokens, ${cost:.4f})")
                    clear_eleves_cache()
                    action_performed = True
                except Exception as e:
                    st.error(f"Erreur: {e}")
        return action_performed

    # Editable text
    synthese_texte = synthese.get("synthese_texte", "")
    new_text = st.text_area(
        "Texte de la synthèse",
        value=synthese_texte,
        height=180,
        key=f"synthese_text_{eleve_id}",
    )

    # Insights
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Alertes**")
        alertes = synthese.get("alertes", [])
        if alertes:
            for alerte in alertes:
                st.caption(
                    f"• {alerte.get('matiere', '?')}: {alerte.get('description', '')}"
                )
        else:
            st.caption("Aucune")

    with col2:
        st.markdown("**Réussites**")
        reussites = synthese.get("reussites", [])
        if reussites:
            for reussite in reussites:
                st.caption(
                    f"• {reussite.get('matiere', '?')}: {reussite.get('description', '')}"
                )
        else:
            st.caption("Aucune")

    # Posture and axes (compact)
    posture = synthese.get("posture_generale")
    axes = synthese.get("axes_travail", [])
    if posture or axes:
        info_parts = []
        if posture:
            info_parts.append(f"Posture: {posture}")
        if axes:
            info_parts.append(f"Axes: {', '.join(axes)}")
        st.caption(" | ".join(info_parts))

    st.divider()

    # Actions
    col1, col2, col3 = st.columns(3)

    with col1:
        text_changed = new_text != synthese_texte
        if st.button("Sauvegarder", key=f"save_{eleve_id}", disabled=not text_changed):
            if synthese_id:
                try:
                    client.update_synthese(synthese_id, synthese_texte=new_text)
                    st.success("Sauvegardé")
                    clear_eleves_cache()
                    action_performed = True
                except Exception as e:
                    st.error(f"Erreur: {e}")

    with col2:
        if st.button("Valider ✓", key=f"validate_{eleve_id}", type="primary"):
            if synthese_id:
                try:
                    client.validate_synthese(synthese_id)
                    st.success("Validée")
                    clear_eleves_cache()
                    action_performed = True
                except Exception as e:
                    st.error(f"Erreur: {e}")

    with col3:
        if st.button("Régénérer", key=f"regen_{eleve_id}"):
            with st.spinner(f"Régénération via {provider}..."):
                try:
                    if synthese_id:
                        client.delete_synthese(synthese_id)
                    result = client.generate_synthese(
                        eleve_id, trimestre, provider=provider, model=model
                    )
                    meta = result.get("metadata", {})
                    tokens = meta.get("tokens_total", "?")
                    st.success(f"Régénérée ({tokens} tokens)")
                    clear_eleves_cache()
                    action_performed = True
                except Exception as e:
                    st.error(f"Erreur: {e}")

    return action_performed
