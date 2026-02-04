"""Import PDF page."""

import sys
from pathlib import Path

# Add project root and app dir to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "app"))

import streamlit as st
from components.sidebar import render_sidebar
from config import LLM_PROVIDERS, get_api_client, ui_settings

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

st.markdown(f"**Classe:** {classe_id} | **Trimestre:** T{trimestre}")

st.divider()

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

    st.divider()

    # Options
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        import_btn = st.button(
            "Importer",
            type="primary",
            use_container_width=True,
        )

    with col2:
        auto_generate = st.checkbox(
            "Auto-générer synthèses",
            value=False,
            help="Générer automatiquement les synthèses après l'import",
        )

    # LLM settings for auto-generation (expandable)
    if auto_generate:
        with st.expander("Paramètres LLM", expanded=False):
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
                model_options = ["(défaut)"] + provider_config["models"]
                model = st.selectbox(
                    "Modèle",
                    options=model_options,
                    index=0,
                    key="import_llm_model",
                )
                if model == "(défaut)":
                    model = None
    else:
        provider = ui_settings.default_provider
        model = None

    if import_btn:
        progress_bar = st.progress(0)
        status_text = st.empty()

        results = []
        imported_eleve_ids = []
        total = len(uploaded_files)

        # Phase 1: Import PDFs
        for i, file in enumerate(uploaded_files):
            status_text.text(f"Import de {file.name}...")
            progress_bar.progress((i + 0.5) / total)

            try:
                content = file.read()
                result = client.import_pdf(content, file.name, classe_id, trimestre)
                results.append(
                    {"file": file.name, "status": "success", "result": result}
                )
                imported_eleve_ids.extend(result.get("eleve_ids", []))
            except Exception as e:
                results.append({"file": file.name, "status": "error", "error": str(e)})

            progress_bar.progress((i + 1) / total)

        progress_bar.empty()
        status_text.empty()

        # Results
        st.markdown("### Résultats de l'import")

        success_count = sum(1 for r in results if r["status"] == "success")
        error_count = sum(1 for r in results if r["status"] == "error")

        col1, col2 = st.columns(2)
        col1.metric("Succès", success_count)
        col2.metric("Erreurs", error_count)

        for r in results:
            if r["status"] == "success":
                result = r["result"]
                st.success(
                    f"{r['file']}: {result.get('imported_count', 0)} élève(s) importé(s)"
                )
                if result.get("eleve_ids"):
                    st.caption(f"IDs: {', '.join(result['eleve_ids'])}")
            else:
                st.error(f"{r['file']}: {r['error']}")

        # Phase 2: Auto-generate syntheses if enabled
        if auto_generate and imported_eleve_ids:
            st.divider()
            st.markdown("### Génération automatique des synthèses")

            gen_progress = st.progress(0)
            gen_status = st.empty()
            gen_success = 0
            gen_error = 0
            total_tokens = 0

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
                    total_tokens += meta.get("tokens_total", 0) or 0
                except Exception:
                    gen_error += 1

                gen_progress.progress((i + 1) / len(imported_eleve_ids))

            gen_progress.empty()
            gen_status.empty()

            col1, col2 = st.columns(2)
            col1.metric("Synthèses générées", gen_success)
            col2.metric("Tokens utilisés", total_tokens)

            if gen_error > 0:
                st.warning(f"{gen_error} erreur(s) de génération")

        st.divider()

        if st.button("Aller à Review", type="primary"):
            st.switch_page("pages/2_review.py")

else:
    st.info("Sélectionnez un ou plusieurs fichiers PDF à importer.")

    # Instructions
    with st.expander("Instructions"):
        st.markdown(
            """
1. Sélectionnez la classe et le trimestre dans la barre latérale
2. Déposez les fichiers PDF des bulletins ci-dessus
3. Cliquez sur "Importer"

Les bulletins seront parsés et les données des élèves extraites automatiquement.
Les noms sont pseudonymisés pour la conformité RGPD.
        """
        )
