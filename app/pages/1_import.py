"""Import PDF page."""

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

# Warn about Mistral OCR limitations
try:
    from src.llm.config import settings as _llm_settings

    if _llm_settings.pdf_parser_type.lower() == "mistral_ocr":
        st.info(
            "Parser actif : **Mistral OCR**. "
            "Les matières, notes et absences ne seront pas extraites automatiquement. "
            "Seul le texte brut du bulletin sera disponible."
        )
except Exception:
    pass

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

    # --- Pre-import duplicate check ---
    # Build a fingerprint to detect file changes and avoid redundant API calls
    files_fingerprint = tuple(sorted((f.name, f.size) for f in uploaded_files))
    check_key = (files_fingerprint, classe_id, trimestre)

    if st.session_state.get("_check_key") != check_key:
        # Read all file contents once for both check and import
        file_contents = []
        for f in uploaded_files:
            f.seek(0)
            file_contents.append((f.name, f.read()))
        st.session_state["_file_contents"] = file_contents

        try:
            check_result = client.check_pdf_duplicates(
                file_contents, classe_id, trimestre
            )
            st.session_state["_check_result"] = check_result
            st.session_state["_check_key"] = check_key
        except Exception:
            st.session_state["_check_result"] = None
            st.session_state["_check_key"] = check_key

    check_result = st.session_state.get("_check_result")
    conflicts = check_result.get("conflicts", []) if check_result else []
    unreadable = check_result.get("unreadable", []) if check_result else []

    # Show unreadable files
    if unreadable:
        for item in unreadable:
            st.error(f"{item['filename']}: {item['error']}")

    # Overwrite checkbox + warning banner
    force_overwrite = True
    if conflicts:
        conflict_names = ", ".join(
            f"{c['prenom']} {c['nom']}".strip() for c in conflicts
        )
        force_overwrite = st.checkbox(
            "Écraser les données existantes en cas de doublon",
            value=True,
        )
        if force_overwrite:
            st.warning(
                f"**{len(conflicts)}** élève(s) déjà présent(s) pour cette classe/trimestre : "
                f"{conflict_names}. Leurs données (bulletin + synthèse) seront écrasées."
            )
        else:
            st.info(
                f"**{len(conflicts)}** élève(s) déjà présent(s) seront ignorés : "
                f"{conflict_names}."
            )

    st.divider()

    # Import button
    if st.button("Importer les fichiers", type="primary", width="stretch"):
        progress_bar = st.progress(0)
        status_text = st.empty()

        results = []
        imported_eleve_ids = []
        skipped_eleve_ids = []
        total = len(uploaded_files)

        # Use pre-read file contents
        file_contents = st.session_state.get("_file_contents", [])
        if not file_contents:
            for f in uploaded_files:
                f.seek(0)
                file_contents.append((f.name, f.read()))

        for i, (filename, content) in enumerate(file_contents):
            status_text.text(f"Import de {filename}...")
            progress_bar.progress((i + 0.5) / total)

            try:
                result = client.import_pdf(
                    content,
                    filename,
                    classe_id,
                    trimestre,
                    force_overwrite=force_overwrite,
                )
                results.append(
                    {"file": filename, "status": "success", "result": result}
                )
                imported_eleve_ids.extend(result.get("eleve_ids", []))
                skipped_eleve_ids.extend(result.get("skipped_ids", []))
            except Exception as e:
                results.append({"file": filename, "status": "error", "error": str(e)})

            progress_bar.progress((i + 1) / total)

        progress_bar.empty()
        status_text.empty()

        # Clear cache to refresh data
        clear_eleves_cache()
        # Reset check cache so next rerun re-checks
        st.session_state.pop("_check_key", None)

        # Display results
        st.markdown("### Résultats de l'import")

        error_count = sum(1 for r in results if r["status"] == "error")
        overwritten_count = sum(
            r["result"].get("overwritten_count", 0)
            for r in results
            if r["status"] == "success"
        )
        skipped_count = sum(
            r["result"].get("skipped_count", 0)
            for r in results
            if r["status"] == "success"
        )

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("PDFs traités", len(results))
        col2.metric("Élèves importés", len(imported_eleve_ids))
        col3.metric("Écrasés", overwritten_count)
        col4.metric("Erreurs", error_count)

        # Show overwrites prominently
        if overwritten_count > 0:
            st.info(
                f"{overwritten_count} élève(s) existant(s) écrasé(s) (données et synthèses remplacées)."
            )

        # Show skipped
        if skipped_count > 0:
            st.info(
                f"{skipped_count} élève(s) existant(s) ignoré(s) (données conservées)."
            )

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
                    skipped_ids = result.get("skipped_ids", [])
                    parsed = result.get("parsed_count", 0)

                    if skipped_ids:
                        st.info(f"{r['file']}: élève ignoré (déjà existant)")
                    elif overwritten_ids:
                        st.info(f"{r['file']}: {len(eleve_ids)} élève(s) écrasé(s)")
                    elif eleve_ids:
                        st.success(f"{r['file']}: {len(eleve_ids)} élève(s) importé(s)")
                    elif parsed == 0:
                        st.warning(f"{r['file']}: aucun élève détecté dans le PDF")

                    for w in result.get("warnings", []):
                        st.warning(f"{r['file']}: {w}")
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
        prenom = e.get("prenom") or ""
        nom = e.get("nom") or ""
        display_name = f"{prenom} {nom}".strip() or e["eleve_id"]
        rows.append(
            {
                "Élève": display_name,
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
