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
from config import LLM_PROVIDERS, get_api_client, ui_settings

st.set_page_config(
    page_title=f"Review - {ui_settings.page_title}",
    page_icon=ui_settings.page_icon,
    layout="wide",
)

client = get_api_client()

# Global sidebar
classe_id, trimestre = render_sidebar(client)

# LLM Settings in sidebar
st.sidebar.divider()
st.sidebar.markdown("### Paramètres LLM")

provider_options = list(LLM_PROVIDERS.keys())
default_idx = (
    provider_options.index(ui_settings.default_provider)
    if ui_settings.default_provider in provider_options
    else 0
)

selected_provider = st.sidebar.selectbox(
    "Provider",
    options=provider_options,
    format_func=lambda x: LLM_PROVIDERS[x]["name"],
    index=default_idx,
    key="llm_provider",
)

provider_config = LLM_PROVIDERS[selected_provider]
model_options = ["(défaut)"] + provider_config["models"]
selected_model = st.sidebar.selectbox(
    "Modèle",
    options=model_options,
    index=0,
    key="llm_model_select",
)
if selected_model == "(défaut)":
    st.session_state["llm_model"] = None
else:
    st.session_state["llm_model"] = selected_model

st.sidebar.slider(
    "Température",
    min_value=0.0,
    max_value=1.0,
    value=ui_settings.default_temperature,
    step=0.1,
    key="llm_temperature",
    help="0 = déterministe, 1 = créatif",
)

# Main content
st.title("Review des synthèses")

if not classe_id:
    st.warning("Sélectionnez une classe dans la barre latérale.")
    st.stop()

st.markdown(f"**Classe:** {classe_id} | **Trimestre:** T{trimestre}")

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
col1, col2 = st.columns(2)

provider = st.session_state.get("llm_provider", ui_settings.default_provider)
model = st.session_state.get("llm_model")
temperature = st.session_state.get("llm_temperature", ui_settings.default_temperature)

with col1:
    if st.button("Générer toutes les synthèses", use_container_width=True):
        progress_bar = st.progress(0)
        status_text = st.empty()
        success_count = 0
        error_count = 0
        total_tokens = 0

        for i, eleve in enumerate(eleves):
            eleve_id = eleve["eleve_id"]
            status_text.text(f"Génération {i + 1}/{len(eleves)}: {eleve_id}...")

            try:
                result = client.generate_synthese(
                    eleve_id,
                    trimestre,
                    provider=provider,
                    model=model,
                    temperature=temperature,
                )
                success_count += 1
                meta = result.get("metadata", {})
                total_tokens += meta.get("tokens_total", 0) or 0
            except Exception:
                error_count += 1

            progress_bar.progress((i + 1) / len(eleves))

        progress_bar.empty()
        status_text.empty()

        if success_count > 0:
            st.success(f"{success_count} synthèses générées ({total_tokens} tokens)")
        if error_count > 0:
            st.warning(f"{error_count} erreur(s)")
        st.rerun()

with col2:
    if st.button("Valider toutes les synthèses", use_container_width=True):
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
