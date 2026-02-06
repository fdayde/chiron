"""Generation & Review page."""

import streamlit as st
from api_client import ChironAPIClient
from components.appreciations_view import render_appreciations, render_eleve_header
from components.data_helpers import (
    clear_eleves_cache,
    fetch_classe,
    fetch_eleve,
    fetch_eleve_synthese,
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

# Get class name (cached)
try:
    classe_info = fetch_classe(client, classe_id)
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
# SECTION: LLM CONFIG (always visible)
# =============================================================================

provider, model = render_llm_selector("syntheses")

# =============================================================================
# SECTION: BATCH GENERATION
# =============================================================================

with st.expander("🤖 Génération batch", expanded=counts["missing"] > 0):
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

        @st.dialog("Confirmer la régénération")
        def confirm_regen_all():
            st.warning(
                f"Cette action va régénérer **toutes les {counts['total']} synthèses**."
            )
            st.caption("Les synthèses existantes seront supprimées et recréées.")

            col_cancel, col_confirm = st.columns(2)
            with col_cancel:
                if st.button("Annuler", key="cancel_regen"):
                    st.rerun()
            with col_confirm:
                if st.button("Confirmer", key="do_regen", type="primary"):
                    all_ids = [e["eleve_id"] for e in eleves_data]
                    progress = st.progress(0)
                    status = st.empty()
                    success_count = 0
                    error_count = 0
                    errors = []

                    for i, eid in enumerate(all_ids):
                        status.text(f"Régénération {i + 1}/{len(all_ids)}")
                        try:
                            synth_data = eleves_data[i]
                            if synth_data.get("synthese_id"):
                                client.delete_synthese(synth_data["synthese_id"])
                            client.generate_synthese(
                                eid, trimestre, provider=provider, model=model
                            )
                            success_count += 1
                        except Exception as e:
                            error_count += 1
                            errors.append(f"{eid}: {e}")
                        progress.progress((i + 1) / len(all_ids))

                    progress.empty()
                    status.empty()
                    clear_eleves_cache()

                    if error_count == 0:
                        st.success(f"{success_count} synthèses régénérées")
                    else:
                        st.warning(
                            f"{success_count} régénérées, {error_count} erreur(s)"
                        )
                        for err in errors:
                            st.error(err)
                    st.rerun()

        if st.button("Tout régénérer", key="regen_all_btn"):
            confirm_regen_all()

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


# =============================================================================
# SECTION: STUDENT VIEW (Fragment - only this reruns on navigation)
# =============================================================================
@st.fragment
def render_student_view(
    filtered_eleves: list,
    client_ref: ChironAPIClient,
    trimestre_val: int,
    provider_val: str,
    model_val: str,
):
    """Render student navigation and details as a fragment.

    This fragment reruns independently, avoiding full page reload on navigation.
    """
    # Navigation controls
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.button(
            "◀ Précédent",
            disabled=st.session_state.current_index == 0,
            key="nav_prev",
        ):
            st.session_state.current_index -= 1
            st.rerun(scope="fragment")

    with col2:
        current_pos = st.session_state.current_index + 1
        st.markdown(
            f"<h3 style='text-align: center;'>{current_pos} / {len(filtered_eleves)}</h3>",
            unsafe_allow_html=True,
        )

    with col3:
        if st.button(
            "Suivant ▶",
            disabled=st.session_state.current_index >= len(filtered_eleves) - 1,
            key="nav_next",
        ):
            st.session_state.current_index += 1
            st.rerun(scope="fragment")

    st.divider()

    # Current student
    current = filtered_eleves[st.session_state.current_index]
    eleve_id = current["eleve_id"]

    # Fetch full student data (with matieres) and synthese - cached
    try:
        eleve_full = fetch_eleve(client_ref, eleve_id)
    except Exception as e:
        st.error(f"Erreur chargement élève: {e}")
        eleve_full = None

    try:
        synthese_data = fetch_eleve_synthese(client_ref, eleve_id, trimestre_val)
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
            client=client_ref,
            eleve_id=eleve_id,
            synthese=synthese,
            synthese_id=synthese_id,
            trimestre=trimestre_val,
            provider=provider_val,
            model=model_val,
        )

        if action_done:
            st.rerun(scope="fragment")


# Render the fragment
render_student_view(filtered, client, trimestre, provider, model)

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
