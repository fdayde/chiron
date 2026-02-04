"""Sidebar components with global state management."""

from __future__ import annotations

import streamlit as st
from api_client import ChironAPIClient


def init_session_state():
    """Initialize session state with default values."""
    if "classe_id" not in st.session_state:
        st.session_state.classe_id = None
    if "trimestre" not in st.session_state:
        st.session_state.trimestre = 1


def render_sidebar(client: ChironAPIClient) -> tuple[str | None, int]:
    """Render the global sidebar with class selector.

    Navigation is handled automatically by Streamlit based on pages/ folder.

    Args:
        client: API client instance.

    Returns:
        Tuple of (classe_id, trimestre) from session state.
    """
    init_session_state()

    # Class and trimester selector (global)
    _render_classe_selector(client)

    st.sidebar.divider()

    # New class form
    render_new_classe_form(client)

    return st.session_state.classe_id, st.session_state.trimestre


def _render_classe_selector(client: ChironAPIClient):
    """Render class and trimester selector, storing values in session state."""
    # Get classes
    try:
        classes = client.list_classes()
    except Exception:
        classes = []

    # Class selector
    if classes:
        options = [""] + [c["classe_id"] for c in classes]
        labels = {"": "-- Sélectionner --"}
        labels.update(
            {c["classe_id"]: f"{c['nom']} ({c['niveau'] or 'N/A'})" for c in classes}
        )

        # Find current index
        current_idx = 0
        if st.session_state.classe_id in options:
            current_idx = options.index(st.session_state.classe_id)

        selected = st.sidebar.selectbox(
            "Classe",
            options=options,
            index=current_idx,
            format_func=lambda x: labels.get(x, x),
            key="sidebar_classe_select",
        )

        # Update session state
        st.session_state.classe_id = selected if selected else None
    else:
        st.sidebar.info("Aucune classe")
        st.session_state.classe_id = None

    # Trimester selector
    trimestre = st.sidebar.selectbox(
        "Trimestre",
        options=[1, 2, 3],
        index=st.session_state.trimestre - 1,
        key="sidebar_trimestre_select",
    )
    st.session_state.trimestre = trimestre


def render_new_classe_form(client: ChironAPIClient) -> dict | None:
    """Render form to create a new class.

    Returns:
        Created class dict or None
    """
    with st.sidebar.expander("➕ Nouvelle classe"):
        nom = st.text_input("Nom", placeholder="5eme A", key="new_classe_nom")
        niveau = st.selectbox(
            "Niveau",
            options=["6eme", "5eme", "4eme", "3eme", "2nde", "1ere", "Terminale"],
            key="new_classe_niveau",
        )
        annee = st.text_input(
            "Année scolaire", value="2024-2025", key="new_classe_annee"
        )

        if st.button("Créer", key="create_classe_btn", use_container_width=True):
            if nom:
                try:
                    result = client.create_classe(nom, niveau, annee)
                    st.success(f"Classe {nom} créée!")
                    # Select the new class
                    st.session_state.classe_id = result["classe_id"]
                    st.rerun()
                    return result
                except Exception as e:
                    st.error(f"Erreur: {e}")
            else:
                st.warning("Nom requis")

    return None


# Keep old function for compatibility during transition
def render_classe_selector(
    client: ChironAPIClient, key: str = "classe_select"
) -> tuple[str | None, int]:
    """Legacy function - redirects to session state values."""
    init_session_state()
    return st.session_state.classe_id, st.session_state.trimestre
