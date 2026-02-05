"""Student card component."""

from __future__ import annotations

import streamlit as st


def render_eleve_card(eleve: dict, synthese: dict | None = None) -> None:
    """Render a student information card.

    Args:
        eleve: Student data dict
        synthese: Optional synthesis data dict
    """
    with st.container(border=True):
        # Header
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            st.markdown(f"### {eleve['eleve_id']}")
            if eleve.get("genre"):
                st.caption(f"{eleve['genre']} - {eleve.get('classe', 'N/A')}")

        with col2:
            absences = eleve.get("absences_demi_journees", 0) or 0
            if absences > 10:
                st.metric("Absences", absences, delta="Elevees", delta_color="inverse")
            else:
                st.metric("Absences", absences)

        with col3:
            retards = eleve.get("retards", 0) or 0
            st.metric("Retards", retards)

        # Subjects summary
        nb_matieres = eleve.get("nb_matieres", 0)
        if nb_matieres:
            st.caption(f"{nb_matieres} matieres")

        # Synthesis status
        if synthese:
            status = synthese.get("status", "unknown")
            if status == "validated":
                st.success("Synthese validee")
            elif status == "edited":
                st.info("Synthese modifiee")
            elif status == "generated":
                st.warning("Synthese generee (a valider)")
            else:
                st.caption(f"Status: {status}")
        else:
            st.caption("Pas de synthese")


def render_eleve_detail(eleve: dict) -> None:
    """Render detailed student information.

    Args:
        eleve: Full student data with matieres
    """
    st.markdown(f"## {eleve['eleve_id']}")

    # Basic info
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Genre", eleve.get("genre", "N/A"))
    col2.metric("Classe", eleve.get("classe", "N/A"))
    col3.metric("Absences", eleve.get("absences_demi_journees", 0) or 0)
    col4.metric("Retards", eleve.get("retards", 0) or 0)

    # Engagements
    engagements = eleve.get("engagements", [])
    if engagements:
        st.markdown("**Engagements:** " + ", ".join(engagements))

    # Parcours
    parcours = eleve.get("parcours", [])
    if parcours:
        st.markdown("**Parcours:** " + ", ".join(parcours))

    # Evenements
    evenements = eleve.get("evenements", [])
    if evenements:
        st.markdown("**Evenements:** " + ", ".join(evenements))

    st.divider()

    # Subjects table
    matieres = eleve.get("matieres", [])
    if matieres:
        st.markdown("### Matieres")

        for matiere in matieres:
            with st.expander(
                f"**{matiere['nom']}** - {matiere.get('moyenne_eleve', 'N/A')}/20"
            ):
                col1, col2 = st.columns(2)
                with col1:
                    st.caption(f"Professeur: {matiere.get('professeur', 'N/A')}")
                    st.caption(
                        f"Moyenne classe: {matiere.get('moyenne_classe', 'N/A')}"
                    )
                with col2:
                    st.markdown(f"*{matiere.get('appreciation', '')}*")
