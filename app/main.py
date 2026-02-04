"""Chiron - Assistant IA pour les conseils de classe."""

import sys
from pathlib import Path

# Add project root to path for src imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
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

# Fetch data
try:
    classes = client.list_classes()
except Exception:
    classes = []

# Metrics row
col1, col2, col3 = st.columns(3)

total_eleves = 0
total_syntheses = 0
total_pending = 0

# Calculate totals
for classe in classes:
    try:
        eleves = client.get_eleves(classe["classe_id"])
        total_eleves += len(eleves)
    except Exception:
        pass

try:
    pending = client.get_pending_syntheses()
    total_pending = pending.get("count", 0)
except Exception:
    pass

col1.metric("Classes", len(classes))
col2.metric("Élèves importés", total_eleves)
col3.metric("Synthèses en attente", total_pending)

# Classes table
if classes:
    st.markdown("#### Détail par classe")

    table_data = []
    for classe in classes:
        classe_id = classe["classe_id"]
        nom = classe["nom"]

        # Get eleves for each trimester
        for trimestre in [1, 2, 3]:
            try:
                eleves = client.get_eleves(classe_id, trimestre)
                if not eleves:
                    continue

                # Count syntheses
                syntheses_count = 0
                validated_count = 0
                for eleve in eleves:
                    try:
                        data = client.get_eleve_synthese(eleve["eleve_id"], trimestre)
                        if data.get("synthese"):
                            syntheses_count += 1
                            if data.get("status") == "validated":
                                validated_count += 1
                    except Exception:
                        pass

                table_data.append(
                    {
                        "Classe": nom,
                        "Trimestre": f"T{trimestre}",
                        "Élèves": len(eleves),
                        "Synthèses": f"{syntheses_count}/{len(eleves)}",
                        "Validées": f"{validated_count}/{syntheses_count}"
                        if syntheses_count
                        else "-",
                    }
                )
            except Exception:
                pass

    if table_data:
        st.dataframe(
            table_data,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Aucune donnée importée pour le moment.")
else:
    st.info("Aucune classe créée. Utilisez le formulaire dans la barre latérale.")

st.divider()

# Guide
st.subheader("Comment utiliser Chiron ?")

st.markdown(
    """
**1. Import** — Déposez les bulletins PDF des élèves
- Sélectionnez une classe et un trimestre dans la barre latérale
- Allez sur la page **Import** et déposez vos fichiers PDF
- Les données sont extraites et pseudonymisées automatiquement

**2. Review** — Générez et validez les synthèses
- Sur la page **Review**, générez les synthèses avec l'IA
- Relisez et modifiez si nécessaire
- Validez chaque synthèse

**3. Export** — Récupérez vos synthèses
- Sur la page **Export**, téléchargez le CSV
- Les noms réels sont restaurés automatiquement
"""
)

st.divider()
st.caption(
    "Les données personnelles (noms) sont stockées localement et ne quittent jamais votre machine."
)
