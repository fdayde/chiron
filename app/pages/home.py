"""Page d'accueil NiceGUI — Dashboard Chiron."""

from cache import check_api_health, fetch_classe_stats, fetch_classes
from layout import page_layout
from nicegui import ui

from src.llm.config import settings as llm_settings


@ui.page("/")
def home_page():
    """Page d'accueil avec état des lieux et workflow."""
    with page_layout("Chiron"):
        ui.label("Assistant IA pour la préparation des conseils de classe").classes(
            "text-subtitle1 text-grey-7"
        )

        # --- API key check ---
        has_key = any(
            [
                llm_settings.openai_api_key,
                llm_settings.anthropic_api_key,
                llm_settings.mistral_api_key,
            ]
        )
        if not has_key:
            with (
                ui.card()
                .classes("w-full q-mt-md")
                .style(
                    "background: rgba(255, 152, 0, 0.12); "
                    "border: 1px solid rgba(255, 152, 0, 0.3)"
                )
            ):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("vpn_key").classes("text-orange text-xl")
                    ui.markdown(
                        "**Clé API manquante** — Aucune clé API n'est configurée. "
                        "La génération de synthèses ne fonctionnera pas."
                    ).classes("text-orange-3")
                ui.markdown(
                    "Créez un fichier **`.env`** à la racine du projet "
                    "(copiez `.env.example`) et ajoutez au moins une clé :\n\n"
                    "```\nANTHROPIC_API_KEY=sk-ant-...\n"
                    "OPENAI_API_KEY=sk-...\n"
                    "MISTRAL_API_KEY=...\n```\n\n"
                    "Puis relancez l'application."
                ).classes("text-body2 q-ml-lg text-grey-4")

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

        # CSS to hide arrows on small screens
        ui.add_head_html("""
        <style>
        @media (max-width: 768px) {
            .workflow-arrow { display: none !important; }
        }
        </style>
        """)

        with ui.row().classes("q-mt-md gap-4 flex-wrap justify-center"):
            _workflow_card(
                "1. Classe",
                "Importez vos bulletins PDF",
                ["Extraction automatique des notes", "Pseudonymisation RGPD"],
                accent="#D4843E",
            )
            ui.icon("arrow_forward").classes(
                "text-3xl text-grey-5 self-center workflow-arrow"
            )
            _workflow_card(
                "2. Synthèses",
                "L'IA génère, vous validez",
                ["Données pseudonymisées", "Calibrage par vos corrections"],
                accent="#4A5899",
            )
            ui.icon("arrow_forward").classes(
                "text-3xl text-grey-5 self-center workflow-arrow"
            )
            _workflow_card(
                "3. Export",
                "Téléchargez les synthèses",
                ["Noms réels restaurés", "Prêt pour le conseil"],
                accent="#C8A45C",
            )

        # --- Privacy notice ---
        with (
            ui.card()
            .classes("w-full q-mt-lg")
            .style(
                "background: rgba(74, 88, 153, 0.12); "
                "border: 1px solid rgba(74, 88, 153, 0.3)"
            )
        ):
            with ui.row().classes("items-center gap-2"):
                ui.icon("lock").style("color: #C8A45C")
                ui.markdown(
                    "**Confidentialité garantie** : Les noms des élèves sont "
                    "pseudonymisés avant tout traitement IA. "
                    "Les données personnelles restent sur votre machine."
                ).classes("text-grey-4")

            with ui.expansion("Détail des données personnelles").classes(
                "w-full q-mt-sm"
            ):
                ui.table(
                    columns=[
                        {
                            "name": "donnee",
                            "label": "Donnée",
                            "field": "donnee",
                            "align": "left",
                        },
                        {
                            "name": "statut",
                            "label": "Traitement",
                            "field": "statut",
                            "align": "left",
                        },
                    ],
                    rows=[
                        {
                            "donnee": "Nom, prénom",
                            "statut": "Pseudonymisé (ELEVE_XXX) avant envoi à l'IA",
                        },
                        {
                            "donnee": "Genre (F/G)",
                            "statut": "Stocké localement, non transmis — le LLM déduit le genre des accords grammaticaux",
                        },
                        {
                            "donnee": "Absences, retards",
                            "statut": "Stocké localement, non transmis",
                        },
                        {
                            "donnee": "Moyennes par matière",
                            "statut": "Catégorisées* avant envoi à l'IA",
                        },
                        {
                            "donnee": "Appréciations enseignantes",
                            "statut": "Transmises pseudonymisées à l'IA",
                        },
                        {
                            "donnee": "Engagements (délégué...)",
                            "statut": "Stocké localement, non transmis",
                        },
                        {
                            "donnee": "Nom des professeurs",
                            "statut": "Stocké localement, non transmis",
                        },
                        {
                            "donnee": "Établissement",
                            "statut": "Stocké localement, non transmis",
                        },
                        {
                            "donnee": "Classe (niveau, groupe)",
                            "statut": "Stocké localement, non transmis",
                        },
                        {
                            "donnee": "Année scolaire",
                            "statut": "Stocké localement, non transmis",
                        },
                        {
                            "donnee": "Trimestre",
                            "statut": "Stocké localement, non transmis",
                        },
                    ],
                ).props("flat bordered dense").classes("w-full")
                ui.label(
                    "* Notes catégorisées selon l'échelle de maîtrise du socle commun (LSU) :"
                    " Insuffisante < 8 · Fragile 8-12 · Satisfaisante 12-16 · Très bonne ≥ 16"
                ).classes("text-caption text-grey-7 q-mt-xs")

                ui.separator().classes("q-mt-sm")

                with ui.row().classes("items-center gap-2 q-mt-sm"):
                    ui.icon("gavel", size="sm").classes("text-grey-6")
                    ui.label("Base légale et responsabilité").classes(
                        "text-weight-bold text-grey-5"
                    )
                ui.markdown(
                    "Le traitement des données scolaires par Chiron s'inscrit dans "
                    "le cadre de la **mission de service public éducatif** "
                    "(RGPD, Article 6(1)(e)). Les données personnelles des élèves "
                    "sont pseudonymisées avant tout envoi à un service externe. "
                    "Les données sont stockées **localement sur votre machine** "
                    "et leur protection relève de votre responsabilité en tant "
                    "qu'utilisateur."
                ).classes("text-caption text-grey-7")
                ui.markdown(
                    "Une fois les synthèses exportées, utilisez le bouton "
                    "**Purge trimestrielle** (page Export) pour supprimer les "
                    "données du trimestre conformément au principe de "
                    "**limitation de la conservation** (Art. 5(1)(e))."
                ).classes("text-caption text-grey-7")

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
            ).props("outline rounded")
            ui.button(
                "Synthèses",
                icon="smart_toy",
                on_click=lambda: ui.navigate.to("/syntheses"),
            ).props("outline rounded")
            ui.button(
                "Exporter",
                icon="download",
                on_click=lambda: ui.navigate.to("/export"),
            ).props("outline rounded")


def _metric_card(label: str, value: str) -> None:
    """Affiche une carte métrique simple (Phase 0, sans delta)."""
    with ui.card().classes("p-3 min-w-40").style("border-left: 3px solid #D4843E"):
        ui.label(label).classes("text-caption text-grey-7")
        ui.label(value).classes("text-h5 text-weight-bold")


def _workflow_card(title: str, subtitle: str, bullets: list[str], accent: str) -> None:
    """Affiche une carte d'étape du workflow."""
    with ui.card().classes("p-4 w-64").style(f"border-top: 3px solid {accent}"):
        ui.label(title).classes("text-h6")
        ui.label(subtitle).classes("text-body2 text-grey-7")
        for bullet in bullets:
            with ui.row().classes("items-center gap-1 no-wrap"):
                ui.icon("arrow_right").classes("flex-none").style(f"color: {accent}")
                ui.label(bullet).classes("text-body2 text-weight-bold")
