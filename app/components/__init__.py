"""UI components."""

from app.components.eleve_card import render_eleve_card, render_eleve_detail
from app.components.sidebar import render_classe_selector, render_new_classe_form
from app.components.synthese_editor import render_synthese_editor

__all__ = [
    "render_classe_selector",
    "render_new_classe_form",
    "render_eleve_card",
    "render_eleve_detail",
    "render_synthese_editor",
]
