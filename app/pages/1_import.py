"""Import PDF page."""

import sys
from pathlib import Path

# Add project root and app dir to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "app"))

import streamlit as st
from components.data_helpers import (
    clear_eleves_cache,
    fetch_classe,
    fetch_eleves_with_syntheses,
    get_status_counts,
)
from components.sidebar import render_sidebar
from config import get_api_client, ui_settings

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

# Get class name (cached)
try:
    classe_info = fetch_classe(client, classe_id)
    classe_nom = classe_info.get("nom", classe_id)
except Exception:
    classe_nom = classe_id

st.markdown(f"**Classe:** {classe_nom} | **Trimestre:** T{trimestre}")

st.divider()

# =============================================================================
# SECTION 1: FILE UPLOAD & IMPORT
# =============================================================================

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

    # Check for existing students
    try:
        eleves_data = fetch_eleves_with_syntheses(client, classe_id, trimestre)
        counts = get_status_counts(eleves_data)
        if counts["total"] > 0:
            details = f"**{counts['total']} élève(s)** existant(s)"
            if counts["with_synthese"] > 0:
                details += f" dont **{counts['with_synthese']}** avec synthèse"
            st.warning(f"{details} seront écrasés.")
    except Exception:
        pass

    st.divider()

    # Import button
    if st.button("Importer les fichiers", type="primary", width="stretch"):
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
                imported_eleve_ids.extend(result.get("eleve_ids", []))
                imported_eleve_ids.extend(result.get("skipped_ids", []))
            except Exception as e:
                results.append({"file": file.name, "status": "error", "error": str(e)})

            progress_bar.progress((i + 1) / total)

        progress_bar.empty()
        status_text.empty()

        # Clear cache to refresh data
        clear_eleves_cache()

        # Display results
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

        # Show errors prominently
        if error_count > 0:
            for r in results:
                if r["status"] == "error":
                    st.error(f"{r['file']}: {r['error']}")

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

        if error_count == 0:
            st.success(
                "Import terminé. Passez à l'étape suivante pour générer les synthèses."
            )
        elif error_count == len(results):
            st.error("Aucun fichier n'a pu être importé.")
        else:
            st.warning(
                f"Import partiel : {len(results) - error_count} fichier(s) importé(s), {error_count} erreur(s)."
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
4. Vérifiez les résultats
5. Passez à la page **Synthèses** pour générer et revoir

Les noms des élèves sont pseudonymisés automatiquement (conformité RGPD).
        """
        )

# =============================================================================
# SECTION 2: CLASS OVERVIEW
# =============================================================================

st.divider()
st.markdown("### Vue de la classe")

try:
    eleves_data = fetch_eleves_with_syntheses(client, classe_id, trimestre)
    counts = get_status_counts(eleves_data)
except Exception as e:
    st.error(f"Erreur: {e}")
    eleves_data = []
    counts = {
        "total": 0,
        "with_synthese": 0,
        "validated": 0,
        "pending": 0,
        "missing": 0,
    }

if counts["total"] == 0:
    st.info("Aucun élève importé pour cette classe/trimestre.")
else:
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Élèves", counts["total"])
    col2.metric("Synthèses", counts["with_synthese"])
    col3.metric("Validées", counts["validated"])
    col4.metric("Manquantes", counts["missing"])

    # Table
    rows = []
    for e in eleves_data:
        rows.append(
            {
                "Élève": e["eleve_id"],
                "Genre": e.get("genre") or "?",
                "Abs.": e.get("absences_demi_journees", 0) or 0,
                "Synthèse": "✓" if e.get("has_synthese") else "-",
                "Statut": e.get("synthese_status", "-") or "-",
            }
        )

    st.dataframe(rows, width="stretch", hide_index=True)

    # Navigation to Review
    st.divider()

    if counts["missing"] > 0:
        st.info(f"🔄 {counts['missing']} élève(s) sans synthèse")

    if counts["pending"] > 0:
        st.info(f"⏳ {counts['pending']} synthèse(s) en attente de validation")

    if st.button("Générer et revoir les synthèses →", type="primary", width="stretch"):
        st.switch_page("pages/2_syntheses.py")
