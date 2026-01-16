"""Import PDF page."""

import streamlit as st

from app.api_client import ChironAPIClient
from app.components.sidebar import render_classe_selector, render_new_classe_form
from app.config import ui_settings

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

    # Import button
    col1, col2 = st.columns([1, 3])

    with col1:
        import_btn = st.button(
            "Importer",
            type="primary",
            use_container_width=True,
        )

    if import_btn:
        progress_bar = st.progress(0)
        status_text = st.empty()

        results = []
        total = len(uploaded_files)

        for i, file in enumerate(uploaded_files):
            status_text.text(f"Import de {file.name}...")
            progress_bar.progress((i + 1) / total)

            try:
                content = file.read()
                result = client.import_pdf(content, file.name, classe_id, trimestre)
                results.append(
                    {"file": file.name, "status": "success", "result": result}
                )
            except Exception as e:
                results.append({"file": file.name, "status": "error", "error": str(e)})

        progress_bar.empty()
        status_text.empty()

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
