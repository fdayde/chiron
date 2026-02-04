"""Export page."""

import sys
from pathlib import Path

# Add project root and app dir to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "app"))

import streamlit as st
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

# Main content
st.title("Export des synthèses")

if not classe_id:
    st.warning("Sélectionnez une classe dans la barre latérale.")
    st.stop()

st.markdown(f"**Classe:** {classe_id} | **Trimestre:** T{trimestre}")

st.divider()

# Get students and syntheses
try:
    eleves = client.get_eleves(classe_id, trimestre)
except Exception as e:
    st.error(f"Erreur: {e}")
    eleves = []

# Count validated syntheses
validated_count = 0
syntheses_data = []

for eleve in eleves:
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
            if data.get("status") == "validated":
                validated_count += 1
    except Exception:
        pass

# Statistics
col1, col2, col3 = st.columns(3)
col1.metric("Total élèves", len(eleves))
col2.metric("Synthèses générées", len(syntheses_data))
col3.metric("Synthèses validées", validated_count)

st.divider()

# Preview
st.markdown("### Aperçu")

if syntheses_data:
    # Filter options
    filter_status = st.selectbox(
        "Filtrer par statut",
        options=["Toutes", "Validées uniquement", "En attente uniquement"],
    )

    filtered = syntheses_data
    if filter_status == "Validées uniquement":
        filtered = [s for s in syntheses_data if s["status"] == "validated"]
    elif filter_status == "En attente uniquement":
        filtered = [s for s in syntheses_data if s["status"] != "validated"]

    st.caption(f"{len(filtered)} synthèse(s)")

    # Table preview
    for item in filtered[:10]:  # Show first 10
        with st.container(border=True):
            col1, col2 = st.columns([1, 4])

            with col1:
                st.markdown(f"**{item['eleve_id']}**")
                status_icon = "✅" if item["status"] == "validated" else "⏳"
                st.caption(f"{status_icon} {item['status']}")

            with col2:
                synthese = item["synthese"]
                text = synthese.get("synthese_texte", "")
                st.markdown(text[:200] + "..." if len(text) > 200 else text)

                # Insights summary
                alertes = synthese.get("alertes", [])
                reussites = synthese.get("reussites", [])
                if alertes or reussites:
                    st.caption(f"Alertes: {len(alertes)} | Réussites: {len(reussites)}")

    if len(filtered) > 10:
        st.caption(f"... et {len(filtered) - 10} autre(s)")

else:
    st.info("Aucune synthèse à exporter.")
    st.markdown("Générez des synthèses depuis la page **Review**.")
    if st.button("Aller à Review"):
        st.switch_page("pages/2_review.py")
    st.stop()

st.divider()

# Export actions
st.markdown("### Export")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### CSV")
    st.caption("Export des synthèses validées au format CSV")

    if validated_count == 0:
        st.warning("Aucune synthèse validée à exporter.")
    else:
        if st.button("Télécharger CSV", type="primary", use_container_width=True):
            try:
                csv_content = client.export_csv(classe_id, trimestre)
                st.download_button(
                    label="Sauvegarder le fichier",
                    data=csv_content,
                    file_name=f"syntheses_{classe_id}_T{trimestre}.csv",
                    mime="text/csv",
                )
            except Exception as e:
                st.error(f"Erreur: {e}")

with col2:
    st.markdown("#### Presse-papiers")
    st.caption("Copier les synthèses pour coller dans un document")

    if st.button("Copier au presse-papiers", use_container_width=True):
        # Build text content
        lines = []
        for item in filtered:
            synthese = item["synthese"]
            lines.append(f"# {item['eleve_id']}")
            lines.append(synthese.get("synthese_texte", ""))
            lines.append("")

        text_content = "\n".join(lines)

        # Use st.code with copy button
        st.code(text_content, language=None)
        st.caption("Utilisez Ctrl+A puis Ctrl+C pour copier")
