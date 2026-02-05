"""Export page."""

import sys
from pathlib import Path

# Add project root and app dir to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "app"))

import streamlit as st
from components.data_helpers import fetch_eleves_with_syntheses, get_status_counts
from components.sidebar import render_sidebar
from config import get_api_client, ui_settings

st.set_page_config(
    page_title=f"Export - {ui_settings.page_title}",
    page_icon=ui_settings.page_icon,
    layout="wide",
)

client = get_api_client()

# Global sidebar
classe_id, trimestre = render_sidebar(client)

# =============================================================================
# HEADER
# =============================================================================

st.title("Export & Bilan")

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

# =============================================================================
# SECTION: RÉCAPITULATIF
# =============================================================================

st.markdown("### 📊 Récapitulatif")

# Fetch data
try:
    eleves_data = fetch_eleves_with_syntheses(client, classe_id, trimestre)
    counts = get_status_counts(eleves_data)
except Exception as e:
    st.error(f"Erreur: {e}")
    st.stop()

# Stats élèves
col1, col2, col3, col4 = st.columns(4)
col1.metric("Élèves", counts["total"])
col2.metric("Synthèses générées", counts["with_synthese"])
col3.metric("Synthèses validées", counts["validated"])
col4.metric("En attente", counts["pending"])

# Stats coûts LLM
try:
    stats = client.get_classe_stats(classe_id, trimestre)

    st.markdown("### 💰 Coûts de génération")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tokens entrée", f"{stats.get('tokens_input', 0):,}")
    col2.metric("Tokens sortie", f"{stats.get('tokens_output', 0):,}")
    col3.metric("Tokens total", f"{stats.get('tokens_total', 0):,}")
    col4.metric("Coût total", f"${stats.get('cost_usd', 0):.4f}")
except Exception:
    pass  # Stats non disponibles, on skip silencieusement

st.divider()

# =============================================================================
# SECTION: WARNINGS
# =============================================================================

if counts["missing"] > 0:
    missing_ids = [e["eleve_id"] for e in eleves_data if not e.get("has_synthese")]
    with st.container(border=True):
        st.warning(f"⚠️ **{counts['missing']} élève(s) sans synthèse**")
        st.caption(f"IDs: {', '.join(missing_ids[:10])}")
        if len(missing_ids) > 10:
            st.caption(f"... et {len(missing_ids) - 10} autre(s)")
        if st.button("Aller générer →"):
            st.switch_page("pages/2_review.py")

if counts["pending"] > 0:
    pending_ids = [
        e["eleve_id"]
        for e in eleves_data
        if e.get("has_synthese") and e.get("synthese_status") != "validated"
    ]
    with st.container(border=True):
        st.info(f"ℹ️ **{counts['pending']} synthèse(s) non validée(s)**")
        st.caption(f"IDs: {', '.join(pending_ids[:10])}")
        if len(pending_ids) > 10:
            st.caption(f"... et {len(pending_ids) - 10} autre(s)")

if counts["total"] == 0:
    st.info("Aucun élève importé. Commencez par importer des bulletins.")
    if st.button("Aller à Import"):
        st.switch_page("pages/1_import.py")
    st.stop()

if counts["validated"] == 0:
    st.warning("Aucune synthèse validée à exporter.")
    if st.button("Aller valider →"):
        st.switch_page("pages/2_review.py")
    st.stop()

st.divider()

# =============================================================================
# SECTION: PREVIEW
# =============================================================================

st.markdown("### 👁️ Aperçu")

# Get full syntheses for preview
syntheses_data = []
for eleve in eleves_data:
    if not eleve.get("has_synthese"):
        continue
    try:
        data = client.get_eleve_synthese(eleve["eleve_id"], trimestre)
        synthese = data.get("synthese")
        if synthese:
            syntheses_data.append(
                {
                    "eleve_id": eleve["eleve_id"],
                    "synthese": synthese,
                    "status": data.get("status", "unknown"),
                }
            )
    except Exception:
        pass

# Filter options
filter_status = st.selectbox(
    "Filtrer par statut",
    options=["Toutes", "Validées uniquement", "En attente uniquement"],
)

if filter_status == "Validées uniquement":
    filtered = [s for s in syntheses_data if s["status"] == "validated"]
elif filter_status == "En attente uniquement":
    filtered = [s for s in syntheses_data if s["status"] != "validated"]
else:
    filtered = syntheses_data

st.caption(f"{len(filtered)} synthèse(s)")

# Preview cards
for item in filtered[:5]:
    with st.container(border=True):
        col1, col2 = st.columns([1, 4])

        with col1:
            st.markdown(f"**{item['eleve_id']}**")
            status_icon = "✅" if item["status"] == "validated" else "⏳"
            st.caption(f"{status_icon} {item['status']}")

        with col2:
            synthese = item["synthese"]
            text = synthese.get("synthese_texte", "")
            st.markdown(text[:250] + "..." if len(text) > 250 else text)

            # Insights summary
            alertes = synthese.get("alertes", [])
            reussites = synthese.get("reussites", [])
            if alertes or reussites:
                st.caption(f"Alertes: {len(alertes)} | Réussites: {len(reussites)}")

if len(filtered) > 5:
    st.caption(f"... et {len(filtered) - 5} autre(s)")

st.divider()

# =============================================================================
# SECTION: EXPORT
# =============================================================================

st.markdown("### 📤 Export")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### CSV")
    st.caption("Export des synthèses validées au format CSV")

    if counts["validated"] == 0:
        st.warning("Aucune synthèse validée")
    else:
        try:
            csv_content = client.export_csv(classe_id, trimestre)
            st.download_button(
                label=f"Télécharger CSV ({counts['validated']} synthèses)",
                data=csv_content,
                file_name=f"syntheses_{classe_id}_T{trimestre}.csv",
                mime="text/csv",
                type="primary",
                width="stretch",
            )
        except Exception as e:
            st.error(f"Erreur: {e}")

with col2:
    st.markdown("#### Presse-papiers")
    st.caption("Copier les synthèses pour coller dans un document")

    if st.button("Préparer pour copie", width="stretch"):
        # Build text content from validated syntheses
        validated_syntheses = [s for s in syntheses_data if s["status"] == "validated"]

        lines = []
        for item in validated_syntheses:
            synthese = item["synthese"]
            lines.append(f"# {item['eleve_id']}")
            lines.append(synthese.get("synthese_texte", ""))
            lines.append("")

        text_content = "\n".join(lines)

        st.text_area(
            "Contenu à copier (Ctrl+A puis Ctrl+C)",
            value=text_content,
            height=200,
        )
        st.caption(f"{len(validated_syntheses)} synthèse(s) validée(s)")
