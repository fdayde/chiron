"""Chiron — Point d'entrée NiceGUI (API + UI dans un seul process).

Usage:
    python run.py                        # Mode web (ouvre le navigateur)
    CHIRON_NATIVE=1 python run.py        # Mode desktop (pywebview)
    CHIRON_PORT=9000 python run.py       # Port personnalisé
"""

import logging
import multiprocessing
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env early so LOG_LEVEL, SHOW_PROMPT etc. are available via os.getenv
load_dotenv(Path(__file__).parent / ".env")


def _setup_logging() -> None:
    """Configure le logging de l'application.

    Niveau par défaut : INFO (les données personnelles ne sont jamais loguées).
    Les logs contenant des noms/prénoms sont au niveau DEBUG uniquement.

    Pour le développement, définir LOG_LEVEL=DEBUG dans .env afin de
    voir les mappings pseudonymisation (noms réels → ELEVE_XXX).
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


_setup_logging()
# Suppress noisy httpx/httpcore cleanup warnings (Event loop is closed)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Setup paths — in frozen mode (PyInstaller), source files live in _internal/
if getattr(sys, "frozen", False):
    project_root = Path(sys.executable).parent
    _internal = project_root / "_internal"
    _app_root = _internal  # app/ is inside _internal/
    sys.path.insert(0, str(_internal))
    sys.path.insert(0, str(_internal / "app"))
else:
    project_root = Path(__file__).parent
    _app_root = project_root  # app/ is at project root
    sys.path.insert(0, str(project_root))
    sys.path.insert(0, str(project_root / "app"))

from src import __version__

# Configure port and API client URL before any import that might use it
_PORT = int(os.getenv("CHIRON_PORT", "8080"))
os.environ.setdefault("CHIRON_UI_API_BASE_URL", f"http://localhost:{_PORT}")

if __name__ == "__main__":
    # Required on Windows: prevents child processes from re-executing this module
    multiprocessing.freeze_support()

    from nicegui import app, ui

    from src.api.routers import (
        classes_router,
        eleves_router,
        exports_router,
        syntheses_router,
    )
    from src.core.constants import ensure_data_directories
    from src.storage.connection import managed_connection

    # --- Close PyInstaller splash screen (frozen mode only) ---
    if getattr(sys, "frozen", False):
        try:
            import pyi_splash  # type: ignore[import-not-found]

            pyi_splash.close()
        except ImportError:
            pass

    # --- Ensure data directories exist ---
    ensure_data_directories()

    # --- Database lifecycle (with = flush WAL on exit) ---
    try:
        with managed_connection():
            # --- RGPD: effacement automatique des données expirées (Art. 5(1)(e)) ---
            import cache as _cache_module

            _cache_module.startup_deletion_result = (
                _cache_module.auto_delete_expired_data()
            )

            # --- Mount existing FastAPI routers ---
            app.include_router(classes_router, prefix="/classes", tags=["Classes"])
            app.include_router(eleves_router, prefix="/eleves", tags=["Eleves"])
            app.include_router(
                syntheses_router, prefix="/syntheses", tags=["Syntheses"]
            )
            app.include_router(exports_router, tags=["Import/Export"])

            @app.get("/health")
            def health():
                """Health check endpoint."""
                return {"status": "ok"}

            # --- Static files ---
            app.add_static_files("/static", str(_app_root / "app" / "static"))

            # --- Import NiceGUI pages (registers @ui.page decorators) ---
            import pages.export  # noqa: F401
            import pages.home  # noqa: F401
            import pages.import_page  # noqa: F401
            import pages.prompt  # noqa: F401
            import pages.references  # noqa: F401
            import pages.syntheses  # noqa: F401

            # --- Launch ---
            native = os.getenv("CHIRON_NATIVE", "0") == "1"
            # window_size activates native mode in NiceGUI (pywebview),
            # so only pass it when native mode is explicitly requested.
            ui.run(
                title=f"Chiron v{__version__}",
                favicon=str(_app_root / "app" / "static" / "chiron_logo.png"),
                port=_PORT,
                native=native,
                window_size=(1400, 900) if native else None,
                reload=False,
                storage_secret=os.getenv(
                    "CHIRON_STORAGE_SECRET", "chiron-local-secret"
                ),
                reconnect_timeout=30.0,
            )
    except KeyboardInterrupt:
        pass
