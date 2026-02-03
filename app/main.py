"""Chiron - Assistant IA pour les conseils de classe."""

import sys
from pathlib import Path

# Add project root to path for src imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
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


# Sidebar
st.sidebar.title("Chiron")
st.sidebar.markdown("*Assistant Conseil de Classe*")
st.sidebar.divider()

# API Status
api_ok = check_api_connection()
if api_ok:
    st.sidebar.success("API connectee")
else:
    st.sidebar.error("API non disponible")
    st.sidebar.caption(f"URL: {ui_settings.api_base_url}")

st.sidebar.divider()
st.sidebar.markdown("### Navigation")
st.sidebar.page_link("main.py", label="Accueil", icon="🏠")
st.sidebar.page_link("pages/1_import.py", label="Import PDF", icon="📄")
st.sidebar.page_link("pages/2_review.py", label="Review", icon="✏️")
st.sidebar.page_link("pages/3_export.py", label="Export", icon="📤")

# Main content
st.title("Chiron")
st.markdown("### Assistant IA pour la preparation des conseils de classe")

st.divider()

if not api_ok:
    st.warning(
        "L'API n'est pas disponible. Lancez le serveur avec:\n\n"
        "```bash\npython -m uvicorn src.api.main:app --port 8000\n```"
    )
    st.stop()

# Dashboard
col1, col2, col3 = st.columns(3)

client = get_api_client()

# Classes count
try:
    classes = client.list_classes()
    col1.metric("Classes", len(classes))
except Exception:
    col1.metric("Classes", "?")

# Pending syntheses
try:
    pending = client.get_pending_syntheses()
    col2.metric("Syntheses en attente", pending.get("count", 0))
except Exception:
    col2.metric("Syntheses en attente", "?")

col3.metric("Trimestre actuel", "1")

st.divider()

# Quick actions
st.markdown("### Actions rapides")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("#### 1. Importer")
    st.markdown("Importez les bulletins PDF des eleves")
    if st.button("Importer des PDFs", type="primary", use_container_width=True):
        st.switch_page("pages/1_import.py")

with col2:
    st.markdown("#### 2. Generer & Valider")
    st.markdown("Generez et validez les syntheses")
    if st.button("Review syntheses", type="primary", use_container_width=True):
        st.switch_page("pages/2_review.py")

with col3:
    st.markdown("#### 3. Exporter")
    st.markdown("Exportez les syntheses validees")
    if st.button("Exporter CSV", type="primary", use_container_width=True):
        st.switch_page("pages/3_export.py")
