"""Prompt page — Affiche le prompt utilisé pour la génération."""

import streamlit as st
from config import get_api_client, ui_settings

st.set_page_config(
    page_title=f"Prompt - {ui_settings.page_title}",
    page_icon=ui_settings.page_icon,
    layout="wide",
)

client = get_api_client()

st.title("Prompt de génération")

try:
    prompt_data = client.get_current_prompt()
except Exception as e:
    st.error(f"Erreur lors du chargement du prompt : {e}")
    st.stop()

# Header info
col1, col2, col3 = st.columns(3)
col1.metric("Template", prompt_data["name"])
col2.metric("Version", prompt_data["version"])
col3.metric("Hash", prompt_data["prompt_hash"])

st.caption(prompt_data.get("description", ""))

st.divider()

# System prompt
st.markdown("### System prompt")
st.caption("Instructions envoyées au LLM avant les données de l'élève.")
st.code(prompt_data["system_prompt"], language=None)

st.divider()

# User prompt template
st.markdown("### User prompt (template)")
st.caption(
    "Message envoyé pour chaque élève. "
    "`{eleve_data}` est remplacé par les données du bulletin."
)
st.code(prompt_data["user_prompt_template"], language=None)
