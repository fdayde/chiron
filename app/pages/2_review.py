"""Review syntheses page."""

import sys
from pathlib import Path

# Add project root and app dir to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "app"))

import streamlit as st
from components.eleve_card import render_eleve_detail
from components.sidebar import render_sidebar
from components.synthese_editor import render_synthese_editor
from config import get_api_client, ui_settings

st.set_page_config(
    page_title=f"Review - {ui_settings.page_title}",
    page_icon=ui_settings.page_icon,
    layout="wide",
)

client = get_api_client()

# Global sidebar
classe_id, trimestre = render_sidebar(client)

# Main content
st.title("Review des synthèses")

if not classe_id:
    st.warning("Sélectionnez une classe dans la barre latérale.")
    st.stop()

# Get class name
try:
    classe_info = client.get_classe(classe_id)
    classe_nom = classe_info.get("nom", classe_id)
except Exception:
    classe_nom = classe_id

st.markdown(f"**Classe:** {classe_nom} | **Trimestre:** T{trimestre}")

st.divider()

# Get students
try:
    eleves = client.get_eleves(classe_id, trimestre)
except Exception as e:
    st.error(f"Erreur lors du chargement des élèves: {e}")
    eleves = []

if not eleves:
    st.info("Aucun élève dans cette classe pour ce trimestre.")
    st.markdown("Importez des bulletins PDF depuis la page **Import**.")
    if st.button("Aller à Import"):
        st.switch_page("pages/1_import.py")
    st.stop()

# Statistics
col1, col2, col3, col4 = st.columns(4)
col1.metric("Élèves", len(eleves))

try:
    pending = client.get_pending_syntheses(classe_id)
    pending_count = pending.get("count", 0)
except Exception:
    pending_count = 0

col2.metric("En attente", pending_count)
col3.metric("Validées", len(eleves) - pending_count)
col4.metric("Trimestre", f"T{trimestre}")

st.divider()

# Batch actions
st.markdown("### Actions groupées")

if st.button("Valider toutes les synthèses", width="stretch"):
    try:
        pending = client.get_pending_syntheses(classe_id)
        validated = 0
        for item in pending.get("pending", []):
            synthese_id = item.get("synthese_id")
            if synthese_id:
                client.validate_synthese(synthese_id)
                validated += 1
        st.success(f"{validated} synthèses validées!")
        st.rerun()
    except Exception as e:
        st.error(f"Erreur: {e}")

st.divider()

# Student list
st.markdown("### Élèves")

if "selected_eleve" not in st.session_state:
    st.session_state.selected_eleve = None

# Two-column layout: list + detail
col_list, col_detail = st.columns([1, 2])

with col_list:
    for eleve in eleves:
        eleve_id = eleve["eleve_id"]

        try:
            synthese_data = client.get_eleve_synthese(eleve_id, trimestre)
            synthese = synthese_data.get("synthese")
        except Exception:
            synthese = None

        with st.container(border=True):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"**{eleve_id}**")
                if synthese:
                    status = (
                        "validée"
                        if synthese_data.get("status") == "validated"
                        else "en attente"
                    )
                    st.caption(f"Synthèse: {status}")
                else:
                    st.caption("Pas de synthèse")

            with col2:
                if st.button("Voir", key=f"view_{eleve_id}"):
                    st.session_state.selected_eleve = eleve_id

with col_detail:
    if st.session_state.selected_eleve:
        eleve_id = st.session_state.selected_eleve

        try:
            eleve = client.get_eleve(eleve_id)
            render_eleve_detail(eleve)
        except Exception as e:
            st.error(f"Erreur: {e}")

        st.divider()

        try:
            synthese_data = client.get_eleve_synthese(eleve_id, trimestre)
            synthese = synthese_data.get("synthese")
            synthese_id = synthese_data.get("synthese_id")
        except Exception:
            synthese = None
            synthese_id = None

        render_synthese_editor(client, eleve_id, synthese, synthese_id, trimestre)

    else:
        st.info("Sélectionnez un élève pour voir ses détails.")
