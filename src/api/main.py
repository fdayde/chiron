"""Application FastAPI Chiron."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.config import api_settings
from src.api.routers import (
    classes_router,
    eleves_router,
    exports_router,
    syntheses_router,
)
from src.storage.connection import get_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise les tables de la base au démarrage."""
    conn = get_connection()
    conn.ensure_tables()
    yield


app = FastAPI(
    title="Chiron API",
    description="API pour l'assistant IA de préparation des conseils de classe",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=api_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(classes_router, prefix="/classes", tags=["Classes"])
app.include_router(eleves_router, prefix="/eleves", tags=["Eleves"])
app.include_router(syntheses_router, prefix="/syntheses", tags=["Syntheses"])
app.include_router(exports_router, tags=["Import/Export"])


@app.get("/health")
def health():
    """Endpoint de vérification de santé."""
    return {"status": "ok"}


@app.get("/")
def root():
    """Endpoint racine avec infos de l'API."""
    return {
        "name": "Chiron API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
