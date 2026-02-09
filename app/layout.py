"""Layout partagé pour toutes les pages NiceGUI."""

from contextlib import contextmanager
from datetime import date

from cache import (
    check_api_health,
    clear_classes_cache,
    fetch_classes,
)
from nicegui import ui
from state import get_classe_id, get_trimestre, set_classe_id, set_trimestre


def _get_current_school_year() -> str:
    """Année scolaire courante au format 'YYYY-YYYY+1' (sept à août)."""
    today = date.today()
    if today.month >= 9:
        return f"{today.year}-{today.year + 1}"
    return f"{today.year - 1}-{today.year}"


@contextmanager
def page_layout(title: str):
    """Layout commun : header + drawer (sidebar) + contenu.

    Args:
        title: Titre affiché en haut de la page.
    """
    ui.dark_mode(True)
    ui.colors(primary="#5C6BC0")

    ui.add_head_html("""
    <style>
    .q-card { transition: transform 0.15s, box-shadow 0.15s; }
    .q-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
    </style>
    """)

    # --- Header ---
    current_path = ui.context.client.page.path

    with ui.header().classes("items-center justify-between"):
        with ui.row().classes("items-center gap-2"):
            ui.button(icon="menu", on_click=lambda: drawer.toggle()).props(
                "flat color=white"
            )
            ui.icon("school").classes("text-2xl")
            ui.label("Chiron").classes("text-h6 text-white")

        with ui.row().classes("gap-1"):
            for label, path in [
                ("Accueil", "/"),
                ("Import", "/import"),
                ("Synthèses", "/syntheses"),
                ("Export", "/export"),
                ("Prompt", "/prompt"),
            ]:
                btn = ui.button(label, on_click=lambda p=path: ui.navigate.to(p)).props(
                    "flat color=white size=sm"
                )
                if current_path == path:
                    btn.style("border-bottom: 2px solid white")

    # --- Drawer (sidebar) ---
    with (
        ui.left_drawer(value=True)
        .classes("q-pa-sm")
        .style("border-right: 1px solid rgba(255,255,255,0.1)") as drawer
    ):
        _render_drawer_content()

    # --- Page content ---
    with ui.column().classes("w-full p-4 max-w-7xl mx-auto"):
        ui.label(title).classes("text-h5 q-mb-sm")
        ui.separator()
        yield


def _render_drawer_content() -> None:
    """Rendu du contenu de la sidebar : santé API, sélecteurs, formulaire."""
    # API health indicator
    api_ok = check_api_health()
    if api_ok:
        with ui.row().classes("items-center gap-2 q-mb-md"):
            ui.icon("check_circle").classes("text-positive")
            ui.label("API connectée").classes("text-positive text-caption")
    else:
        with ui.row().classes("items-center gap-2 q-mb-md"):
            ui.icon("error").classes("text-negative")
            ui.label("API indisponible").classes("text-negative text-caption")

    # --- Class selector ---
    try:
        classes = fetch_classes()
    except Exception:
        classes = []

    if classes:
        options = {
            c["classe_id"]: f"{c['nom']} ({c['niveau'] or 'N/A'})" for c in classes
        }

        current = get_classe_id()
        if current and current not in options:
            current = None
            set_classe_id(None)

        def _on_classe_change(e):
            set_classe_id(e.value)
            ui.navigate.to(ui.context.client.page.path)

        ui.select(
            options=options,
            label="Classe",
            value=current,
            clearable=True,
            on_change=_on_classe_change,
        ).classes("w-full")
    else:
        ui.label("Aucune classe").classes("text-grey-6 q-mb-sm")

    # --- Trimester selector ---
    def _on_trimestre_change(e):
        set_trimestre(e.value)
        ui.navigate.to(ui.context.client.page.path)

    ui.select(
        options={1: "Trimestre 1", 2: "Trimestre 2", 3: "Trimestre 3"},
        label="Trimestre",
        value=get_trimestre(),
        on_change=_on_trimestre_change,
    ).classes("w-full q-mt-sm")

    ui.separator().classes("q-my-md")

    # --- New class form ---
    with ui.expansion("Nouvelle classe", icon="add").classes("w-full"):
        _render_new_classe_form()


def _render_new_classe_form() -> None:
    """Formulaire de création de classe dans le drawer."""
    niveaux = ["6eme", "5eme", "4eme", "3eme", "2nde", "1ere", "Terminale"]

    niveau_select = ui.select(
        options=niveaux,
        label="Niveau",
        value="6eme",
    ).classes("w-full")

    groupe_input = ui.input(
        label="Groupe",
        placeholder="A",
    ).classes("w-full")

    annee_input = ui.input(
        label="Année scolaire",
        value=_get_current_school_year(),
    ).classes("w-full")

    ui.label("Format : {niveau}{groupe}_{année} (ex: 3A_2024-2025)").classes(
        "text-caption text-grey-6 q-mt-xs"
    )

    async def create_classe():
        groupe = groupe_input.value
        if not groupe:
            ui.notify("Le groupe est requis (ex: A, B, 1...)", type="negative")
            return

        niveau = niveau_select.value
        annee = annee_input.value
        nom = f"{niveau[0]}{groupe}_{annee}"

        try:
            from src.api.dependencies import get_classe_repo
            from src.storage.repositories.classe import Classe

            repo = get_classe_repo()
            classe = Classe(classe_id="", nom=nom, niveau=niveau, annee_scolaire=annee)
            classe_id = repo.create(classe)
            clear_classes_cache()
            set_classe_id(classe_id)
            ui.notify(f"Classe {nom} créée !", type="positive")
            await ui.run_javascript("location.reload()")
        except Exception as e:
            ui.notify(f"Erreur : {e}", type="negative")

    ui.button("Créer", on_click=create_classe, icon="add").classes("w-full q-mt-sm")
