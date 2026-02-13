"""Layout partagé pour toutes les pages NiceGUI."""

from contextlib import contextmanager
from datetime import date

from cache import (
    check_api_health,
    clear_classes_cache,
    fetch_classes,
)
from nicegui import ui
from state import (
    get_classe_id,
    get_llm_model,
    get_llm_provider,
    get_trimestre,
    set_classe_id,
    set_llm_model,
    set_llm_provider,
    set_trimestre,
)

from src import __version__


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
    ui.colors(primary="#4A5899")

    ui.add_head_html(
        '<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">'
    )
    ui.add_head_html("""
    <style>
    :root {
        --chiron-navy: #2D3561;
        --chiron-blue: #4A5899;
        --chiron-terracotta: #D4843E;
        --chiron-gold: #C8A45C;
    }
    body { font-family: 'Inter', sans-serif; }
    .chiron-title { font-family: 'Cinzel', serif; letter-spacing: 0.05em; }
    .q-card {
        transition: transform 0.15s, box-shadow 0.15s;
        border-radius: 12px !important;
        border: 1px solid rgba(255,255,255,0.08);
    }
    .q-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 3px; }
    /* Loading overlay */
    #chiron-loading {
        position: fixed; inset: 0; z-index: 9999;
        display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        background: #1a1e2e;
        transition: opacity 0.4s ease;
    }
    #chiron-loading.fade-out { opacity: 0; pointer-events: none; }
    #chiron-loading img {
        width: 128px; height: 128px;
        animation: pulse 1.8s ease-in-out infinite;
    }
    #chiron-loading p {
        margin-top: 1.2rem; color: var(--chiron-gold);
        font-family: 'Cinzel', serif; font-size: 0.9rem;
        letter-spacing: 0.05em;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.5; transform: scale(0.95); }
    }
    </style>
    """)

    # Loading overlay — only on first page load, not on subsequent navigations
    ui.add_body_html("""
    <div id="chiron-loading">
        <img src="/static/chiron_logo.png" alt="Chiron">
        <p>Chargement en cours…</p>
    </div>
    <script>
    if (sessionStorage.getItem('chiron-loaded')) {
        document.getElementById('chiron-loading')?.remove();
    } else {
        sessionStorage.setItem('chiron-loaded', '1');
        const _obs = new MutationObserver(() => {
            const app = document.getElementById('app');
            if (app && !app.classList.contains('nicegui-unocss-loading')) {
                const overlay = document.getElementById('chiron-loading');
                if (overlay) {
                    overlay.classList.add('fade-out');
                    setTimeout(() => overlay.remove(), 500);
                }
                _obs.disconnect();
            }
        });
        _obs.observe(document.body, { attributes: true, subtree: true, attributeFilter: ['class'] });
    }
    </script>
    """)

    # --- Header ---
    current_path = ui.context.client.page.path

    with (
        ui.header()
        .classes("items-center justify-between")
        .style("background: linear-gradient(135deg, #4A5899, #2D3561)")
    ):
        with ui.row().classes("items-center gap-2"):
            ui.button(icon="menu", on_click=lambda: drawer.toggle()).props(
                "flat color=white"
            )
            ui.html('<img src="/static/chiron_logo.png" width="64" height="64">')
            ui.label("Chiron").classes("text-h6 text-white chiron-title")

        with ui.row().classes("gap-1"):
            for label, path in [
                ("Accueil", "/"),
                ("Classe", "/import"),
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
        _render_drawer_content(current_path)

    # --- Page content ---
    with ui.column().classes("w-full p-4 max-w-7xl mx-auto"):
        ui.label(title).classes("text-h5 q-mb-sm")
        ui.separator()
        yield

        # --- Footer ---
        ui.separator().classes("q-mt-lg")
        with ui.row().classes("w-full justify-center items-center gap-2 q-mt-sm"):
            ui.label(
                f"© 2025-2026 Florent Dayde — All rights reserved — v{__version__}"
            ).classes("text-caption text-grey-7")
            ui.label("·").classes("text-caption text-grey-7")
            ui.link(
                "GitHub",
                "https://github.com/fdayde/chiron",
                new_tab=True,
            ).classes("text-caption")


def _render_drawer_content(current_path: str = "") -> None:
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

    # --- LLM selector (only on /syntheses) ---
    if current_path == "/syntheses":
        ui.separator().classes("q-my-md")
        _render_llm_selector()

    ui.separator().classes("q-my-md")

    # --- New class form ---
    with ui.expansion("Nouvelle classe", icon="add").classes("w-full"):
        _render_new_classe_form()


def _render_llm_selector() -> None:
    """Render LLM provider/model selectors in the sidebar."""
    from config_ng import LLM_PROVIDERS, format_model_label

    with ui.row().classes("items-center gap-1"):
        ui.icon("smart_toy", size="xs").classes("text-primary")
        ui.label("Modele IA").classes("text-weight-bold text-caption")

    provider_keys = list(LLM_PROVIDERS.keys())
    provider_options = {k: LLM_PROVIDERS[k]["name"] for k in provider_keys}

    current_provider = get_llm_provider()
    if current_provider not in provider_options:
        current_provider = provider_keys[0]

    current_model = get_llm_model()
    models = LLM_PROVIDERS[current_provider]["models"]
    model_options = {m: format_model_label(current_provider, m) for m in models}
    if current_model not in model_options:
        current_model = LLM_PROVIDERS[current_provider].get("default", "")
        if current_model not in model_options and models:
            current_model = models[0]

    # Initialize state
    set_llm_provider(current_provider)
    set_llm_model(current_model)

    model_select = None

    def _on_provider_change(e):
        nonlocal model_select
        prov = e.value
        set_llm_provider(prov)
        new_models = LLM_PROVIDERS[prov]["models"]
        new_options = {m: format_model_label(prov, m) for m in new_models}
        model_select.options = new_options
        new_default = LLM_PROVIDERS[prov].get("default", "")
        new_val = (
            new_default
            if new_default in new_options
            else (new_models[0] if new_models else None)
        )
        model_select.value = new_val
        model_select.update()
        set_llm_model(new_val)

    def _on_model_change(e):
        set_llm_model(e.value)

    ui.select(
        options=provider_options,
        label="Provider",
        value=current_provider,
        on_change=_on_provider_change,
    ).classes("w-full q-mt-xs")

    model_select = ui.select(
        options=model_options,
        label="Modele",
        value=current_model,
        on_change=_on_model_change,
    ).classes("w-full q-mt-xs")


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

    ui.button("Créer", on_click=create_classe, icon="add").props("rounded").classes(
        "w-full q-mt-sm"
    )
