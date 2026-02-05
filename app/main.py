"""Chiron - Assistant IA pour les conseils de classe."""

import sys
from pathlib import Path

# Add project root to path for src imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
from components.data_helpers import fetch_classes
from components.sidebar import render_sidebar
from config import get_api_client, ui_settings

st.set_page_config(
    page_title=ui_settings.page_title,
    page_icon=ui_settings.page_icon,
    layout="wide",
    initial_sidebar_state="expanded",
)


def check_api_connection() -> bool:
    """Check if API is available."""
    try:
        client = get_api_client()
        client.health()
        return True
    except Exception:
        return False


# Check API
api_ok = check_api_connection()
client = get_api_client()

# Sidebar (global)
render_sidebar(client)

# API status in sidebar
if api_ok:
    st.sidebar.success("API connectée", icon="✅")
else:
    st.sidebar.error("API non disponible")
    st.sidebar.caption(f"URL: {ui_settings.api_base_url}")

# Main content
st.title("Chiron")
st.caption("Assistant IA pour la préparation des conseils de classe")

if not api_ok:
    st.error(
        "L'API n'est pas disponible. Lancez le serveur avec:\n\n"
        "```bash\npython -m uvicorn src.api.main:app --port 8000\n```"
    )
    st.stop()

st.divider()

# Dashboard - État des lieux
st.subheader("État des lieux")

# Fetch data (cached)
try:
    classes = fetch_classes(client)
except Exception:
    classes = []

# Build stats table using get_classe_stats (optimized: ~15 calls instead of ~450)
table_data = []
total_eleves = 0
total_validated = 0
total_pending = 0

for classe in classes:
    classe_id = classe["classe_id"]
    nom = classe["nom"]

    for trimestre in [1, 2, 3]:
        try:
            stats = client.get_classe_stats(classe_id, trimestre)
            eleve_count = stats.get("eleve_count", 0)
            if eleve_count == 0:
                continue

            synthese_count = stats.get("synthese_count", 0)
            validated_count = stats.get("validated_count", 0)

            total_eleves += eleve_count
            total_validated += validated_count
            total_pending += synthese_count - validated_count

            table_data.append(
                {
                    "Classe": nom,
                    "Trimestre": f"T{trimestre}",
                    "Élèves": eleve_count,
                    "Synthèses": f"{synthese_count}/{eleve_count}",
                    "Validées": f"{validated_count}/{synthese_count}"
                    if synthese_count
                    else "-",
                }
            )
        except Exception:
            pass

# Metrics row
col1, col2, col3 = st.columns(3)
col1.metric("Classes", len(classes))
col2.metric("Élèves importés", total_eleves)
col3.metric("Synthèses en attente", total_pending)

# Classes table
if classes:
    st.markdown("#### Détail par classe")

    if table_data:
        st.dataframe(
            table_data,
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("Aucune donnée importée pour le moment.")
else:
    st.info("Aucune classe créée. Utilisez le formulaire dans la barre latérale.")

st.divider()

# Workflow visuel
st.subheader("Comment ça marche ?")

# Schéma en 3 étapes avec colonnes
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        """
        <div style="text-align: center; padding: 1rem; border-radius: 10px; border: 2px solid #4CAF50; background: rgba(76, 175, 80, 0.1);">
            <div style="font-size: 2.5rem;">📄</div>
            <h3 style="margin: 0.5rem 0;">1. Import</h3>
            <p style="font-size: 0.9rem; color: #666; margin: 0;">
                Déposez vos bulletins PDF<br/>
                <strong>→ Extraction automatique</strong><br/>
                <strong>→ Anonymisation RGPD</strong>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        """
        <div style="text-align: center; padding: 1rem; border-radius: 10px; border: 2px solid #2196F3; background: rgba(33, 150, 243, 0.1);">
            <div style="font-size: 2.5rem;">🤖</div>
            <h3 style="margin: 0.5rem 0;">2. Review</h3>
            <p style="font-size: 0.9rem; color: #666; margin: 0;">
                L'IA génère les synthèses<br/>
                <strong>→ Relecture & correction</strong><br/>
                <strong>→ Validation par l'enseignant</strong>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        """
        <div style="text-align: center; padding: 1rem; border-radius: 10px; border: 2px solid #FF9800; background: rgba(255, 152, 0, 0.1);">
            <div style="font-size: 2.5rem;">📤</div>
            <h3 style="margin: 0.5rem 0;">3. Export</h3>
            <p style="font-size: 0.9rem; color: #666; margin: 0;">
                Téléchargez le CSV final<br/>
                <strong>→ Noms réels restaurés</strong><br/>
                <strong>→ Prêt pour le conseil</strong>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Flèches entre les étapes
st.markdown(
    """
    <div style="display: flex; justify-content: space-around; margin: -1rem 0 1rem 0;">
        <div style="flex: 1;"></div>
        <div style="font-size: 1.5rem; color: #888;">→</div>
        <div style="flex: 1;"></div>
        <div style="font-size: 1.5rem; color: #888;">→</div>
        <div style="flex: 1;"></div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Encart sécurité
st.info(
    "🔒 **Confidentialité garantie** : Les noms des élèves sont pseudonymisés avant tout traitement IA. "
    "Les données personnelles restent sur votre machine."
)

st.divider()

# Quick actions
st.markdown("### Démarrer")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("📄 Importer des bulletins", width="stretch"):
        st.switch_page("pages/1_import.py")

with col2:
    if st.button("🤖 Synthèses", width="stretch"):
        st.switch_page("pages/2_syntheses.py")

with col3:
    if st.button("📤 Exporter", width="stretch"):
        st.switch_page("pages/3_Export.py")
