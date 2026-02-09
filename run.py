"""Chiron — Point d'entrée NiceGUI (API + UI dans un seul process).

Usage:
    python run.py                        # Mode web (ouvre le navigateur)
    CHIRON_NATIVE=1 python run.py        # Mode desktop (pywebview)
    CHIRON_PORT=9000 python run.py       # Port personnalisé
"""

import multiprocessing
import os
import sys
from pathlib import Path

# Setup paths — in frozen mode (PyInstaller), source files live in _internal/
if getattr(sys, "frozen", False):
    project_root = Path(sys.executable).parent
    _internal = project_root / "_internal"
    sys.path.insert(0, str(_internal))
    sys.path.insert(0, str(_internal / "app"))
else:
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    sys.path.insert(0, str(project_root / "app"))

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
    from src.storage.connection import get_connection

    # --- Ensure data directories exist ---
    ensure_data_directories()

    # --- Database initialization ---
    get_connection()

    # --- Mount existing FastAPI routers (same prefixes as src/api/main.py) ---
    app.include_router(classes_router, prefix="/classes", tags=["Classes"])
    app.include_router(eleves_router, prefix="/eleves", tags=["Eleves"])
    app.include_router(syntheses_router, prefix="/syntheses", tags=["Syntheses"])
    app.include_router(exports_router, tags=["Import/Export"])

    @app.get("/health")
    def health():
        """Health check endpoint."""
        return {"status": "ok"}

    # --- Import NiceGUI pages (registers @ui.page decorators) ---
    import pages.export  # noqa: F401
    import pages.home  # noqa: F401
    import pages.import_page  # noqa: F401
    import pages.prompt  # noqa: F401
    import pages.syntheses  # noqa: F401

    # --- Launch ---
    native = os.getenv("CHIRON_NATIVE", "0") == "1"
    ui.run(
        title="Chiron",
        favicon="🏫",
        port=_PORT,
        native=native,
        window_size=(1400, 900),
        reload=False,
        storage_secret=os.getenv("CHIRON_STORAGE_SECRET", "chiron-local-secret"),
        reconnect_timeout=30.0,  # PDF import can take 30s+ (NER model loading)
    )
