"""Page d'accueil NiceGUI — Dashboard Chiron."""

from cache import check_api_health, fetch_classe_stats, fetch_classes
from layout import page_layout
from nicegui import ui


@ui.page("/")
def home_page():
    """Page d'accueil avec état des lieux et workflow."""
    with page_layout("Chiron"):
        ui.label("Assistant IA pour la préparation des conseils de classe").classes(
            "text-subtitle1 text-grey-7"
        )

        # --- API status ---
        api_ok = check_api_health()
        if not api_ok:
            with ui.card().classes("w-full bg-red-10 q-mt-md"):
                ui.label("API non disponible").classes("text-negative text-bold")
                ui.label(
                    "Les routers FastAPI sont montés dans le même process. "
                    "Si cette erreur apparaît, vérifiez les logs de démarrage."
                )
            return

        # --- Metrics ---
        with ui.row().classes("items-center gap-2 q-mt-md"):
            ui.icon("assessment").classes("text-primary")
            ui.label("État des lieux").classes("text-h6")

        classes = []
        try:
            classes = fetch_classes()
        except Exception as e:
            ui.notify(f"Erreur chargement classes: {e}", type="negative")

        total_eleves = 0
        total_pending = 0
        table_rows = []

        for classe in classes:
            classe_id = classe["classe_id"]
            nom = classe["nom"]

            for trimestre in [1, 2, 3]:
                stats = fetch_classe_stats(classe_id, trimestre)
                if not stats:
                    continue

                eleve_count = stats.get("eleve_count", 0)
                if eleve_count == 0:
                    continue

                synthese_count = stats.get("synthese_count", 0)
                validated_count = stats.get("validated_count", 0)

                total_eleves += eleve_count
                total_pending += synthese_count - validated_count

                table_rows.append(
                    {
                        "classe": nom,
                        "trimestre": f"T{trimestre}",
                        "eleves": eleve_count,
                        "syntheses": f"{synthese_count}/{eleve_count}",
                        "validees": f"{validated_count}/{synthese_count}"
                        if synthese_count
                        else "-",
                    }
                )

        with ui.row().classes("q-mt-md gap-4"):
            _metric_card("Classes", str(len(classes)))
            _metric_card("Élèves importés", str(total_eleves))
            _metric_card("Synthèses en attente", str(total_pending))

        # --- Table ---
        if table_rows:
            with ui.row().classes("items-center gap-2 q-mt-md"):
                ui.icon("table_chart").classes("text-primary")
                ui.label("Détail par classe").classes("text-h6")
            ui.table(
                columns=[
                    {"name": "classe", "label": "Classe", "field": "classe"},
                    {"name": "trimestre", "label": "Trimestre", "field": "trimestre"},
                    {"name": "eleves", "label": "Élèves", "field": "eleves"},
                    {"name": "syntheses", "label": "Synthèses", "field": "syntheses"},
                    {"name": "validees", "label": "Validées", "field": "validees"},
                ],
                rows=table_rows,
            ).props("flat bordered dense").classes("w-full q-mt-sm")
        elif classes:
            ui.label("Aucune donnée importée pour le moment.").classes(
                "text-grey-6 q-mt-md"
            )
        else:
            ui.label(
                "Aucune classe créée. Utilisez la barre latérale pour en créer une."
            ).classes("text-grey-6 q-mt-md")

        ui.separator().classes("q-mt-md")

        # --- Workflow ---
        with ui.row().classes("items-center gap-2 q-mt-md"):
            ui.icon("help_outline").classes("text-primary")
            ui.label("Comment ça marche ?").classes("text-h6")

        with ui.row().classes("q-mt-md gap-4 justify-center"):
            _workflow_card(
                "1. Import",
                "Déposez vos bulletins PDF",
                ["Extraction automatique", "Anonymisation RGPD"],
                color="green",
            )
            ui.icon("arrow_forward").classes("text-3xl text-grey-5 self-center")
            _workflow_card(
                "2. Review",
                "L'IA génère les synthèses",
                ["Relecture & correction", "Validation par l'enseignant"],
                color="blue",
            )
            ui.icon("arrow_forward").classes("text-3xl text-grey-5 self-center")
            _workflow_card(
                "3. Export",
                "Téléchargez le CSV final",
                ["Noms réels restaurés", "Prêt pour le conseil"],
                color="orange",
            )

        # --- Privacy notice ---
        with ui.card().classes("w-full bg-blue-10 q-mt-lg"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("lock").classes("text-blue-8")
                ui.markdown(
                    "**Confidentialité garantie** : Les noms des élèves sont "
                    "pseudonymisés avant tout traitement IA. "
                    "Les données personnelles restent sur votre machine."
                )

        ui.separator().classes("q-mt-md")

        # --- Quick actions ---
        with ui.row().classes("items-center gap-2 q-mt-md"):
            ui.icon("rocket_launch").classes("text-primary")
            ui.label("Démarrer").classes("text-h6")
        with ui.row().classes("q-mt-md gap-4"):
            ui.button(
                "Importer des bulletins",
                icon="upload_file",
                on_click=lambda: ui.navigate.to("/import"),
            ).props("outline")
            ui.button(
                "Synthèses",
                icon="smart_toy",
                on_click=lambda: ui.navigate.to("/syntheses"),
            ).props("outline")
            ui.button(
                "Exporter",
                icon="download",
                on_click=lambda: ui.navigate.to("/export"),
            ).props("outline")


def _metric_card(label: str, value: str) -> None:
    """Affiche une carte métrique simple (Phase 0, sans delta)."""
    with (
        ui.card()
        .classes("p-3 min-w-40")
        .style("border-left: 3px solid var(--q-primary)")
    ):
        ui.label(label).classes("text-caption text-grey-7")
        ui.label(value).classes("text-h5 text-weight-bold")


def _workflow_card(title: str, subtitle: str, bullets: list[str], color: str) -> None:
    """Affiche une carte d'étape du workflow."""
    with (
        ui.card()
        .classes(f"p-4 w-64 border-{color}-5")
        .style(f"border-top: 3px solid var(--q-{color})")
    ):
        ui.label(title).classes("text-h6")
        ui.label(subtitle).classes("text-body2 text-grey-7")
        for bullet in bullets:
            with ui.row().classes("items-center gap-1"):
                ui.icon("arrow_right").classes(f"text-{color}")
                ui.label(bullet).classes("text-body2 text-weight-bold")
