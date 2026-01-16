"""Sidebar components."""

from __future__ import annotations

import streamlit as st

from app.api_client import ChironAPIClient


def render_classe_selector(
    client: ChironAPIClient, key: str = "classe_select"
) -> tuple[str | None, int]:
    """Render class and trimester selector in sidebar.

    Returns:
        Tuple of (classe_id, trimestre)
    """
    st.sidebar.markdown("### Filtres")

    # Get classes
    try:
        classes = client.list_classes()
    except Exception:
        classes = []

    # Class selector
    if classes:
        options = {
            c["classe_id"]: f"{c['nom']} ({c['niveau'] or 'N/A'})" for c in classes
        }
        classe_id = st.sidebar.selectbox(
            "Classe",
            options=list(options.keys()),
            format_func=lambda x: options[x],
            key=key,
        )
    else:
        st.sidebar.info("Aucune classe disponible")
        classe_id = None

    # Trimester selector
    trimestre = st.sidebar.selectbox(
        "Trimestre",
        options=[1, 2, 3],
        key=f"{key}_trimestre",
    )

    return classe_id, trimestre


def render_new_classe_form(client: ChironAPIClient) -> dict | None:
    """Render form to create a new class.

    Returns:
        Created class dict or None
    """
    with st.sidebar.expander("Nouvelle classe"):
        nom = st.text_input("Nom", placeholder="5eme A", key="new_classe_nom")
        niveau = st.selectbox(
            "Niveau",
            options=["6eme", "5eme", "4eme", "3eme", "2nde", "1ere", "Terminale"],
            key="new_classe_niveau",
        )
        annee = st.text_input(
            "Annee scolaire", value="2024-2025", key="new_classe_annee"
        )

        if st.button("Creer", key="create_classe_btn"):
            if nom:
                try:
                    result = client.create_classe(nom, niveau, annee)
                    st.success(f"Classe {nom} creee!")
                    st.rerun()
                    return result
                except Exception as e:
                    st.error(f"Erreur: {e}")
            else:
                st.warning("Nom requis")

    return None
