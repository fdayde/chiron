"""Import PDF page."""

import streamlit as st

from app.api_client import ChironAPIClient
from app.components.sidebar import render_classe_selector, render_new_classe_form
from app.config import LLM_PROVIDERS, ui_settings

st.set_page_config(
    page_title=f"Import - {ui_settings.page_title}",
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
st.sidebar.markdown("*Import PDF*")
st.sidebar.divider()

classe_id, trimestre = render_classe_selector(client, key="import_classe")
render_new_classe_form(client)

# Main content
st.title("Import des bulletins PDF")

if not classe_id:
    st.warning("Selectionnez ou creez une classe dans la barre laterale.")
    st.stop()

st.markdown(f"**Classe:** {classe_id} | **Trimestre:** {trimestre}")

st.divider()

# File uploader
uploaded_files = st.file_uploader(
    "Deposez les fichiers PDF des bulletins",
    type=["pdf"],
    accept_multiple_files=True,
    key="pdf_uploader",
)

if uploaded_files:
    st.markdown(f"### {len(uploaded_files)} fichier(s) selectionne(s)")

    # Preview
    with st.expander("Apercu des fichiers"):
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
            "Auto-generer syntheses",
            value=False,
            help="Generer automatiquement les syntheses apres l'import",
        )

    # LLM settings for auto-generation (expandable)
    if auto_generate:
        with st.expander("Parametres LLM", expanded=False):
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
                model_options = ["(defaut)"] + provider_config["models"]
                model = st.selectbox(
                    "Modele",
                    options=model_options,
                    index=0,
                    key="import_llm_model",
                )
                if model == "(defaut)":
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

        # Results
        st.markdown("### Resultats de l'import")

        success_count = sum(1 for r in results if r["status"] == "success")
        error_count = sum(1 for r in results if r["status"] == "error")

        col1, col2 = st.columns(2)
        col1.metric("Succes", success_count)
        col2.metric("Erreurs", error_count)

        for r in results:
            if r["status"] == "success":
                result = r["result"]
                st.success(
                    f"{r['file']}: {result.get('imported_count', 0)} eleve(s) importe(s)"
                )
                if result.get("eleve_ids"):
                    st.caption(f"IDs: {', '.join(result['eleve_ids'])}")
            else:
                st.error(f"{r['file']}: {r['error']}")

        # Phase 2: Auto-generate syntheses if enabled
        if auto_generate and imported_eleve_ids:
            st.divider()
            st.markdown("### Generation automatique des syntheses")

            gen_progress = st.progress(0)
            gen_status = st.empty()
            gen_success = 0
            gen_error = 0
            total_tokens = 0

            for i, eleve_id in enumerate(imported_eleve_ids):
                gen_status.text(
                    f"Generation {i + 1}/{len(imported_eleve_ids)}: {eleve_id}..."
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
            col1.metric("Syntheses generees", gen_success)
            col2.metric("Tokens utilises", total_tokens)

            if gen_error > 0:
                st.warning(f"{gen_error} erreur(s) de generation")

        st.divider()

        if st.button("Aller a la page Review", type="primary"):
            st.switch_page("pages/2_review.py")

else:
    st.info("Selectionnez un ou plusieurs fichiers PDF a importer.")

    # Instructions
    with st.expander("Instructions"):
        st.markdown("""
        1. Selectionnez la classe cible dans la barre laterale
        2. Choisissez le trimestre
        3. Deposez les fichiers PDF des bulletins
        4. Cliquez sur "Importer"

        Les bulletins seront parses et les donnees des eleves extraites automatiquement.
        Les noms sont pseudonymises pour la conformite RGPD.
        """)
