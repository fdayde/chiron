"""Review syntheses page."""

import streamlit as st

from app.api_client import ChironAPIClient
from app.components.eleve_card import render_eleve_detail
from app.components.sidebar import render_classe_selector
from app.components.synthese_editor import render_synthese_editor
from app.config import ui_settings

st.set_page_config(
    page_title=f"Review - {ui_settings.page_title}",
    page_icon=ui_settings.page_icon,
    layout="wide",
)


@st.cache_resource
def get_api_client() -> ChironAPIClient:
    """Get cached API client."""
    return ChironAPIClient()


client = get_api_client()

# Sidebar
st.sidebar.title("Chiron")
st.sidebar.markdown("*Review Syntheses*")
st.sidebar.divider()

classe_id, trimestre = render_classe_selector(client, key="review_classe")

# Main content
st.title("Review des syntheses")

if not classe_id:
    st.warning("Selectionnez une classe dans la barre laterale.")
    st.stop()

st.markdown(f"**Classe:** {classe_id} | **Trimestre:** {trimestre}")

st.divider()

# Get students
try:
    eleves = client.get_eleves(classe_id, trimestre)
except Exception as e:
    st.error(f"Erreur lors du chargement des eleves: {e}")
    eleves = []

if not eleves:
    st.info("Aucun eleve dans cette classe pour ce trimestre.")
    st.markdown("Importez des bulletins PDF depuis la page **Import**.")
    if st.button("Aller a Import"):
        st.switch_page("pages/1_import.py")
    st.stop()

# Statistics
col1, col2, col3, col4 = st.columns(4)
col1.metric("Eleves", len(eleves))

# Get syntheses status
try:
    pending = client.get_pending_syntheses(classe_id)
    pending_count = pending.get("count", 0)
except Exception:
    pending_count = 0

col2.metric("En attente", pending_count)
col3.metric("Validees", len(eleves) - pending_count)
col4.metric("Trimestre", trimestre)

st.divider()

# Batch actions
st.markdown("### Actions groupees")
col1, col2 = st.columns(2)

with col1:
    if st.button("Generer toutes les syntheses", use_container_width=True):
        progress = st.progress(0)
        for i, eleve in enumerate(eleves):
            try:
                client.generate_synthese(eleve["eleve_id"], trimestre)
            except Exception:
                pass  # May already exist
            progress.progress((i + 1) / len(eleves))
        progress.empty()
        st.success("Syntheses generees!")
        st.rerun()

with col2:
    if st.button("Valider toutes les syntheses", use_container_width=True):
        # Get all pending and validate
        try:
            pending = client.get_pending_syntheses(classe_id)
            for item in pending.get("pending", []):
                synthese_id = item.get("synthese_id")
                if synthese_id:
                    client.validate_synthese(synthese_id)
            st.success("Syntheses validees!")
            st.rerun()
        except Exception as e:
            st.error(f"Erreur: {e}")

st.divider()

# Student list
st.markdown("### Eleves")

# Session state for selected student
if "selected_eleve" not in st.session_state:
    st.session_state.selected_eleve = None

# Two-column layout: list + detail
col_list, col_detail = st.columns([1, 2])

with col_list:
    for eleve in eleves:
        eleve_id = eleve["eleve_id"]

        # Get synthese for this student
        try:
            synthese_data = client.get_eleve_synthese(eleve_id, trimestre)
            synthese = synthese_data.get("synthese")
        except Exception:
            synthese = None

        # Card with click
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"**{eleve_id}**")
                if synthese:
                    status = (
                        "validee"
                        if synthese.get("status") == "validated"
                        else "en attente"
                    )
                    st.caption(f"Synthese: {status}")
                else:
                    st.caption("Pas de synthese")

            with col2:
                if st.button("Voir", key=f"view_{eleve_id}"):
                    st.session_state.selected_eleve = eleve_id

with col_detail:
    if st.session_state.selected_eleve:
        eleve_id = st.session_state.selected_eleve

        # Get full student data
        try:
            eleve = client.get_eleve(eleve_id)
            render_eleve_detail(eleve)
        except Exception as e:
            st.error(f"Erreur: {e}")

        st.divider()

        # Get synthese
        try:
            synthese_data = client.get_eleve_synthese(eleve_id, trimestre)
            synthese = synthese_data.get("synthese")
            synthese_id = synthese_data.get("synthese_id")
        except Exception:
            synthese = None
            synthese_id = None

        render_synthese_editor(client, eleve_id, synthese, synthese_id, trimestre)

    else:
        st.info("Selectionnez un eleve pour voir ses details.")
