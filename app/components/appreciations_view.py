"""Appreciations view component for side-by-side layout."""

from __future__ import annotations

import streamlit as st


def render_eleve_header(eleve: dict) -> None:
    """Render compact student header with key metrics.

    Args:
        eleve: Student data dict.
    """
    col1, col2, col3, col4 = st.columns(4)

    genre = eleve.get("genre") or "?"
    col1.metric("Genre", genre)

    absences = eleve.get("absences_demi_journees", 0) or 0
    col2.metric("Absences", absences)

    retards = eleve.get("retards", 0) or 0
    col3.metric("Retards", retards)

    nb_matieres = len(eleve.get("matieres", []))
    col4.metric("Matières", nb_matieres)


def render_appreciations(eleve: dict) -> None:
    """Render subject appreciations in a compact format.

    Designed for side-by-side layout with synthesis.

    Args:
        eleve: Full student data with matieres.
    """
    matieres = eleve.get("matieres", [])

    if not matieres:
        st.info("Aucune matière disponible.")
        return

    for matiere in matieres:
        with st.container(border=True):
            # Header: subject + grade
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"**{matiere['nom']}**")
                prof = matiere.get("professeur", "")
                if prof:
                    st.caption(prof)

            with col2:
                note = matiere.get("moyenne_eleve")
                moy_classe = matiere.get("moyenne_classe")
                if note is not None:
                    delta = None
                    if moy_classe is not None and note is not None:
                        diff = note - moy_classe
                        delta = f"{diff:+.1f}"
                    st.metric("Note", f"{note}/20", delta=delta)

            # Appreciation text
            appreciation = matiere.get("appreciation", "")
            if appreciation:
                st.markdown(f"_{appreciation}_")


def render_appreciations_compact(eleve: dict, max_display: int = 5) -> None:
    """Render appreciations in ultra-compact format.

    Shows only subjects with appreciations, limited count.

    Args:
        eleve: Full student data with matieres.
        max_display: Maximum subjects to show.
    """
    matieres = eleve.get("matieres", [])

    # Filter subjects with appreciations
    with_appreciation = [m for m in matieres if m.get("appreciation")]

    if not with_appreciation:
        st.caption("Aucune appréciation disponible.")
        return

    for matiere in with_appreciation[:max_display]:
        note = matiere.get("moyenne_eleve", "-")
        st.markdown(f"**{matiere['nom']}** ({note}/20)")
        st.caption(matiere.get("appreciation", ""))
        st.markdown("---")

    remaining = len(with_appreciation) - max_display
    if remaining > 0:
        st.caption(f"... et {remaining} autre(s) matière(s)")
