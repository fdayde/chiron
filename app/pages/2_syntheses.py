"""Generation & Review page."""

import sys
from pathlib import Path

# Add project root and app dir to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "app"))

import streamlit as st
from components.appreciations_view import render_appreciations, render_eleve_header
from components.data_helpers import (
    clear_eleves_cache,
    fetch_eleves_with_syntheses,
    get_status_counts,
)
from components.llm_selector import render_cost_estimate, render_llm_selector
from components.sidebar import render_sidebar
from components.synthese_editor import render_synthese_editor
from config import get_api_client, ui_settings

st.set_page_config(
    page_title=f"Synthèses - {ui_settings.page_title}",
    page_icon=ui_settings.page_icon,
    layout="wide",
)

client = get_api_client()

# Global sidebar
classe_id, trimestre = render_sidebar(client)

# =============================================================================
# HEADER
# =============================================================================

st.title("Génération & Review")

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

# Fetch data
try:
    eleves_data = fetch_eleves_with_syntheses(client, classe_id, trimestre)
    counts = get_status_counts(eleves_data)
except Exception as e:
    st.error(f"Erreur: {e}")
    st.stop()

if counts["total"] == 0:
    st.info("Aucun élève dans cette classe. Importez des bulletins d'abord.")
    if st.button("Aller à Import"):
        st.switch_page("pages/1_import.py")
    st.stop()

# Metrics
col1, col2, col3, col4 = st.columns(4)
col1.metric("Élèves", counts["total"])
col2.metric("Générées", counts["with_synthese"])
col3.metric("Validées", counts["validated"])
col4.metric("En attente", counts["pending"])

st.divider()

# =============================================================================
# SECTION: BATCH GENERATION
# =============================================================================

with st.expander("🤖 Génération batch", expanded=counts["missing"] > 0):
    provider, model = render_llm_selector("review")

    col1, col2 = st.columns(2)

    with col1:
        render_cost_estimate(provider, model, counts["missing"])

        if st.button(
            f"Générer manquantes ({counts['missing']})",
            disabled=counts["missing"] == 0,
            width="stretch",
        ):
            # Get IDs without synthese
            missing_ids = [
                e["eleve_id"] for e in eleves_data if not e.get("has_synthese")
            ]

            progress = st.progress(0)
            status = st.empty()
            success_count = 0
            error_count = 0

            for i, eleve_id in enumerate(missing_ids):
                status.text(f"Génération {i + 1}/{len(missing_ids)}: {eleve_id}")
                try:
                    client.generate_synthese(
                        eleve_id, trimestre, provider=provider, model=model
                    )
                    success_count += 1
                except Exception:
                    error_count += 1
                progress.progress((i + 1) / len(missing_ids))

            progress.empty()
            status.empty()
            clear_eleves_cache()

            if error_count > 0:
                st.warning(f"{success_count} générées, {error_count} erreurs")
            else:
                st.success(f"{success_count} synthèses générées")
            st.rerun()

    with col2:
        render_cost_estimate(provider, model, counts["total"])

        if st.button("Tout régénérer", width="stretch"):
            st.warning("Cette action va régénérer toutes les synthèses existantes.")

            if st.button("Confirmer", key="confirm_regen_all"):
                all_ids = [e["eleve_id"] for e in eleves_data]
                progress = st.progress(0)
                status = st.empty()

                for i, eleve_id in enumerate(all_ids):
                    status.text(f"Régénération {i + 1}/{len(all_ids)}")
                    try:
                        # Delete existing if any
                        synth_data = eleves_data[i]
                        if synth_data.get("synthese_id"):
                            client.delete_synthese(synth_data["synthese_id"])
                        client.generate_synthese(
                            eleve_id, trimestre, provider=provider, model=model
                        )
                    except Exception:
                        pass
                    progress.progress((i + 1) / len(all_ids))

                progress.empty()
                status.empty()
                clear_eleves_cache()
                st.success("Régénération terminée")
                st.rerun()

st.divider()

# =============================================================================
# SECTION: NAVIGATION & FILTERS
# =============================================================================

# Filter options
filter_options = {
    "all": "Tous",
    "missing": "Sans synthèse",
    "pending": "Non validées",
    "validated": "Validées",
}

col1, col2 = st.columns([2, 3])

with col1:
    selected_filter = st.radio(
        "Filtrer",
        options=list(filter_options.keys()),
        format_func=lambda x: filter_options[x],
        horizontal=True,
        key="eleve_filter",
    )

# Apply filter
if selected_filter == "missing":
    filtered = [e for e in eleves_data if not e.get("has_synthese")]
elif selected_filter == "pending":
    filtered = [
        e
        for e in eleves_data
        if e.get("has_synthese") and e.get("synthese_status") != "validated"
    ]
elif selected_filter == "validated":
    filtered = [e for e in eleves_data if e.get("synthese_status") == "validated"]
else:
    filtered = eleves_data

with col2:
    st.caption(f"{len(filtered)} élève(s)")

if not filtered:
    st.info("Aucun élève ne correspond au filtre sélectionné.")
    st.stop()

# Navigation state
if "current_index" not in st.session_state:
    st.session_state.current_index = 0

# Ensure index is valid after filter change
if st.session_state.current_index >= len(filtered):
    st.session_state.current_index = 0

# Navigation controls
col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    if st.button(
        "◀ Précédent", disabled=st.session_state.current_index == 0, width="stretch"
    ):
        st.session_state.current_index -= 1
        st.rerun()

with col2:
    current_pos = st.session_state.current_index + 1
    st.markdown(
        f"<h3 style='text-align: center;'>{current_pos} / {len(filtered)}</h3>",
        unsafe_allow_html=True,
    )

with col3:
    if st.button(
        "Suivant ▶",
        disabled=st.session_state.current_index >= len(filtered) - 1,
        width="stretch",
    ):
        st.session_state.current_index += 1
        st.rerun()

st.divider()

# =============================================================================
# SECTION: SIDE-BY-SIDE CONTENT
# =============================================================================

current = filtered[st.session_state.current_index]
eleve_id = current["eleve_id"]

# Fetch full student data (with matieres) and synthese
try:
    eleve_full = client.get_eleve(eleve_id)
except Exception as e:
    st.error(f"Erreur chargement élève: {e}")
    eleve_full = None

try:
    synthese_data = client.get_eleve_synthese(eleve_id, trimestre)
    synthese = synthese_data.get("synthese")
    synthese_id = synthese_data.get("synthese_id")
except Exception:
    synthese = None
    synthese_id = None

# Student header with real name
status_badge = ""
if current.get("synthese_status") == "validated":
    status_badge = " ✅"
elif current.get("has_synthese"):
    status_badge = " ⏳"

# Display real name if available
if eleve_full:
    prenom = eleve_full.get("prenom_reel") or ""
    nom = eleve_full.get("nom_reel") or ""
    nom_complet = f"{prenom} {nom}".strip()
    display_name = nom_complet if nom_complet else eleve_id
else:
    display_name = eleve_id

st.markdown(f"### {display_name}{status_badge}")
st.caption(f"ID: {eleve_id}")

# Two columns: Appreciations | Synthese
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("#### Appréciations")
    if eleve_full:
        render_eleve_header(eleve_full)
        render_appreciations(eleve_full)
    else:
        st.warning("Données élève non disponibles")

with col_right:
    st.markdown("#### Synthèse")
    action_done = render_synthese_editor(
        client=client,
        eleve_id=eleve_id,
        synthese=synthese,
        synthese_id=synthese_id,
        trimestre=trimestre,
        provider=provider,
        model=model,
    )

    if action_done:
        st.rerun()

# =============================================================================
# FOOTER: PROGRESS & NAVIGATION
# =============================================================================

st.divider()

# Progress bar
progress_value = counts["validated"] / counts["total"] if counts["total"] > 0 else 0
st.progress(
    progress_value,
    text=f"Progression : {counts['validated']}/{counts['total']} validées",
)

# Navigation to Export
if counts["validated"] > 0:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Aller à Export →", type="primary", width="stretch"):
            st.switch_page("pages/3_Export.py")
