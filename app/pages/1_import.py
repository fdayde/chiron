"""Import PDF page."""

import sys
from pathlib import Path

# Add project root and app dir to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "app"))

import streamlit as st
from components.sidebar import render_sidebar
from config import (
    LLM_PROVIDERS,
    calculate_actual_cost,
    estimate_total_cost,
    format_model_label,
    get_api_client,
    ui_settings,
)

st.set_page_config(
    page_title=f"Import - {ui_settings.page_title}",
    page_icon=ui_settings.page_icon,
    layout="wide",
)

client = get_api_client()

# Global sidebar
classe_id, trimestre = render_sidebar(client)

# Main content
st.title("Import des bulletins PDF")

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

# Initialize session state for import results
if "import_results" not in st.session_state:
    st.session_state.import_results = None

# File uploader
uploaded_files = st.file_uploader(
    "Déposez les fichiers PDF des bulletins",
    type=["pdf"],
    accept_multiple_files=True,
    key="pdf_uploader",
)

if uploaded_files:
    st.markdown(f"### {len(uploaded_files)} fichier(s) sélectionné(s)")

    # Preview
    with st.expander("Aperçu des fichiers"):
        for f in uploaded_files:
            st.caption(f"- {f.name} ({f.size / 1024:.1f} Ko)")

    # Check for existing students and syntheses
    try:
        existing_eleves = client.get_eleves(classe_id, trimestre)
        existing_count = len(existing_eleves)
        # Count how many have syntheses
        syntheses_count = 0
        for eleve in existing_eleves:
            try:
                synth = client.get_eleve_synthese(eleve["eleve_id"], trimestre)
                if synth and synth.get("synthese"):
                    syntheses_count += 1
            except Exception:
                pass
    except Exception:
        existing_count = 0
        syntheses_count = 0

    if existing_count > 0:
        details = f"**{existing_count} élève(s)** (bulletins)"
        if syntheses_count > 0:
            details += f" dont **{syntheses_count}** avec synthèse"
        st.warning(f"{details} seront écrasés.")

    st.divider()

    # Step 1: Import button
    if st.button("Importer les fichiers", type="primary", use_container_width=True):
        progress_bar = st.progress(0)
        status_text = st.empty()

        results = []
        imported_eleve_ids = []
        total = len(uploaded_files)

        for i, file in enumerate(uploaded_files):
            status_text.text(f"Import de {file.name}...")
            progress_bar.progress((i + 0.5) / total)

            try:
                content = file.read()
                result = client.import_pdf(content, file.name, classe_id, trimestre)
                results.append(
                    {"file": file.name, "status": "success", "result": result}
                )
                # Include both new and existing students
                imported_eleve_ids.extend(result.get("eleve_ids", []))
                imported_eleve_ids.extend(result.get("skipped_ids", []))
            except Exception as e:
                results.append({"file": file.name, "status": "error", "error": str(e)})

            progress_bar.progress((i + 1) / total)

        progress_bar.empty()
        status_text.empty()

        # Store results in session state
        st.session_state.import_results = {
            "results": results,
            "eleve_ids": imported_eleve_ids,
        }

    # Display import results if available
    if st.session_state.import_results:
        results = st.session_state.import_results["results"]
        imported_eleve_ids = st.session_state.import_results["eleve_ids"]

        st.markdown("### Résultats de l'import")

        error_count = sum(1 for r in results if r["status"] == "error")
        overwritten_count = sum(
            r["result"].get("overwritten_count", 0)
            for r in results
            if r["status"] == "success"
        )

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("PDFs traités", len(results))
        col2.metric("Élèves importés", len(imported_eleve_ids))
        col3.metric("Écrasés", overwritten_count)
        col4.metric("Erreurs", error_count)

        # Detail per file
        with st.expander("Détail par fichier"):
            for r in results:
                if r["status"] == "success":
                    result = r["result"]
                    eleve_ids = result.get("eleve_ids", [])
                    overwritten_ids = result.get("overwritten_ids", [])
                    parsed = result.get("parsed_count", 0)

                    if overwritten_ids:
                        st.info(f"{r['file']}: {len(eleve_ids)} élève(s) écrasé(s)")
                        st.caption(f"IDs: {', '.join(eleve_ids)}")
                    elif eleve_ids:
                        st.success(f"{r['file']}: {len(eleve_ids)} élève(s) importé(s)")
                        st.caption(f"IDs anonymisés: {', '.join(eleve_ids)}")
                    elif parsed == 0:
                        st.warning(f"{r['file']}: aucun élève détecté dans le PDF")
                else:
                    st.error(f"{r['file']}: {r['error']}")

        st.divider()

        # Step 2: Generate syntheses button
        if imported_eleve_ids:
            st.markdown("### Génération des synthèses")

            # LLM settings
            col1, col2 = st.columns(2)
            with col1:
                provider = st.selectbox(
                    "Provider",
                    options=list(LLM_PROVIDERS.keys()),
                    format_func=lambda x: LLM_PROVIDERS[x]["name"],
                    index=0,
                    key="import_llm_provider",
                )
            with col2:
                provider_config = LLM_PROVIDERS[provider]
                model_options = provider_config["models"]
                model = st.selectbox(
                    "Modèle",
                    options=model_options,
                    format_func=lambda x: format_model_label(provider, x),
                    index=0,
                    key="import_llm_model",
                )

            # Cost estimation
            nb_eleves = len(imported_eleve_ids)
            total_cost = estimate_total_cost(provider, model, nb_eleves)
            st.caption(
                f"💰 Estimation : **~${total_cost:.4f}** pour {nb_eleves} élève(s)"
            )

            if st.button(
                f"Générer les synthèses ({nb_eleves} élèves)",
                width="stretch",
            ):
                gen_progress = st.progress(0)
                gen_status = st.empty()
                gen_success = 0
                gen_error = 0
                total_tokens_input = 0
                total_tokens_output = 0

                for i, eleve_id in enumerate(imported_eleve_ids):
                    gen_status.text(
                        f"Génération {i + 1}/{len(imported_eleve_ids)}: {eleve_id}..."
                    )

                    try:
                        result = client.generate_synthese(
                            eleve_id,
                            trimestre,
                            provider=provider,
                            model=model,
                        )
                        gen_success += 1
                        meta = result.get("metadata", {})
                        total_tokens_input += meta.get("tokens_input", 0) or 0
                        total_tokens_output += meta.get("tokens_output", 0) or 0
                    except Exception:
                        gen_error += 1

                    gen_progress.progress((i + 1) / len(imported_eleve_ids))

                gen_progress.empty()
                gen_status.empty()

                # Calculate actual cost
                total_tokens = total_tokens_input + total_tokens_output
                actual_cost = calculate_actual_cost(
                    provider, model, total_tokens_input, total_tokens_output
                )

                col1, col2, col3 = st.columns(3)
                col1.metric("Synthèses générées", gen_success)
                col2.metric("Tokens utilisés", f"{total_tokens:,}")
                col3.metric("Coût réel", f"${actual_cost:.4f}")

                if gen_error > 0:
                    st.warning(f"{gen_error} erreur(s) de génération")

                st.info(
                    "Rendez-vous sur la page **Review** pour relire et "
                    "valider les synthèses."
                )

else:
    st.info("Sélectionnez un ou plusieurs fichiers PDF à importer.")

    # Instructions
    with st.expander("Instructions"):
        st.markdown(
            """
1. Sélectionnez la classe et le trimestre dans la barre latérale
2. Déposez les fichiers PDF des bulletins ci-dessus
3. Cliquez sur **Importer les fichiers**
4. Vérifiez les résultats (PDFs traités, élèves importés, anonymisation)
5. Cliquez sur **Générer les synthèses** pour lancer l'IA

Les noms des élèves sont pseudonymisés automatiquement (conformité RGPD).
        """
        )
