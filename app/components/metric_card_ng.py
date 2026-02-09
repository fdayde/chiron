"""MetricCard — Composant NiceGUI remplaçant st.metric."""

from __future__ import annotations

from nicegui import ui


def metric_card(
    label: str,
    value: str | int | float,
    delta: str | None = None,
    delta_color: str = "positive",
    inverse: bool = False,
) -> None:
    """Affiche une carte métrique avec label, valeur et delta optionnel.

    Args:
        label: Libellé au-dessus de la valeur.
        value: Valeur principale affichée.
        delta: Texte de variation (ex: "+2.5", "Élevées").
        delta_color: Couleur Quasar du delta (positive, negative, warning).
        inverse: Si True, positive=rouge et negative=vert (pour les absences).
    """
    if inverse:
        delta_color = "negative" if delta_color == "positive" else "positive"

    with (
        ui.card()
        .classes("p-3 min-w-36")
        .style("border-left: 3px solid var(--q-primary)")
    ):
        ui.label(label).classes("text-caption text-grey-7")
        ui.label(str(value)).classes("text-h5 text-weight-bold")
        if delta is not None:
            ui.label(delta).classes(f"text-caption text-{delta_color}")
