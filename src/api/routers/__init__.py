"""API routers."""

from src.api.routers.classes import router as classes_router
from src.api.routers.eleves import router as eleves_router
from src.api.routers.exports import router as exports_router
from src.api.routers.syntheses import router as syntheses_router

__all__ = ["classes_router", "eleves_router", "syntheses_router", "exports_router"]
