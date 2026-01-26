"""Review syntheses page."""

import streamlit as st

from app.api_client import ChironAPIClient
from app.components.eleve_card import render_eleve_detail
from app.components.sidebar import render_classe_selector
from app.components.synthese_editor import render_synthese_editor
from app.config import LLM_PROVIDERS, ui_settings

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

# LLM Settings in sidebar
st.sidebar.divider()
st.sidebar.markdown("### Parametres LLM")

# Provider selection
provider_options = list(LLM_PROVIDERS.keys())
provider_names = [LLM_PROVIDERS[p]["name"] for p in provider_options]
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

# Model selection based on provider
provider_config = LLM_PROVIDERS[selected_provider]
model_options = ["(defaut)"] + provider_config["models"]
selected_model = st.sidebar.selectbox(
    "Modele",
    options=model_options,
    index=0,
    key="llm_model_select",
)
# Store actual model value (None for default)
if selected_model == "(defaut)":
    st.session_state["llm_model"] = None
else:
    st.session_state["llm_model"] = selected_model

# Temperature
st.sidebar.slider(
    "Temperature",
    min_value=0.0,
    max_value=1.0,
    value=ui_settings.default_temperature,
    step=0.1,
    key="llm_temperature",
    help="0 = deterministe, 1 = creatif",
)

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

# Get LLM settings for batch generation
provider = st.session_state.get("llm_provider", ui_settings.default_provider)
model = st.session_state.get("llm_model")
temperature = st.session_state.get("llm_temperature", ui_settings.default_temperature)

with col1:
    if st.button("Generer toutes les syntheses", use_container_width=True):
        progress_bar = st.progress(0)
        status_text = st.empty()
        success_count = 0
        error_count = 0
        total_tokens = 0
        total_duration = 0

        for i, eleve in enumerate(eleves):
            eleve_id = eleve["eleve_id"]
            status_text.text(f"Generation {i + 1}/{len(eleves)}: {eleve_id}...")

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
                total_duration += meta.get("duration_ms", 0) or 0
            except Exception:
                error_count += 1
                # Continue with next student

            progress_bar.progress((i + 1) / len(eleves))

        progress_bar.empty()
        status_text.empty()

        if success_count > 0:
            st.success(
                f"{success_count} syntheses generees "
                f"({total_tokens} tokens, {total_duration / 1000:.1f}s total)"
            )
        if error_count > 0:
            st.warning(f"{error_count} erreurs (peut-etre deja generes)")
        st.rerun()

with col2:
    if st.button("Valider toutes les syntheses", use_container_width=True):
        # Get all pending and validate
        try:
            pending = client.get_pending_syntheses(classe_id)
            validated = 0
            for item in pending.get("pending", []):
                synthese_id = item.get("synthese_id")
                if synthese_id:
                    client.validate_synthese(synthese_id)
                    validated += 1
            st.success(f"{validated} syntheses validees!")
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
