"""Collecte et gestion des métriques d'appels LLM.

Ce module définit les structures de données pour tracker les appels LLM
et un collector pour les agréger et les exporter vers DuckDB.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import duckdb
from pydantic import BaseModel, Field

from src.core.constants import DATA_LLM_METRICS_DIR, DB_LLM_METRICS

logger = logging.getLogger(__name__)


class LLMCallMetrics(BaseModel):
    """Métriques d'un appel LLM individuel.

    Attributes:
        timestamp: Horodatage de l'appel
        provider: Provider utilisé (openai/anthropic/mistral)
        model: Nom du modèle
        prompt_tokens: Nombre de tokens du prompt
        completion_tokens: Nombre de tokens de la réponse
        total_tokens: Total des tokens
        latency_ms: Latence en millisecondes
        success: Indique si l'appel a réussi
        error_type: Type d'erreur si échec
        cost_usd: Coût estimé en USD
    """

    timestamp: datetime = Field(
        default_factory=datetime.now, description="Horodatage de l'appel"
    )
    provider: str = Field(..., description="Provider (openai/anthropic/mistral)")
    model: str = Field(..., description="Nom du modèle")
    prompt_tokens: int = Field(default=0, ge=0, description="Tokens du prompt")
    completion_tokens: int = Field(
        default=0, ge=0, description="Tokens de la complétion"
    )
    total_tokens: int = Field(default=0, ge=0, description="Total tokens")
    latency_ms: float = Field(default=0.0, ge=0, description="Latence en ms")
    success: bool = Field(..., description="Succès de l'appel")
    error_type: str | None = Field(default=None, description="Type d'erreur")
    cost_usd: float | None = Field(default=None, ge=0, description="Coût en USD")


class MetricsCollector:
    """Collecteur de métriques LLM avec export vers DuckDB.

    Singleton pattern pour centraliser la collecte de métriques.
    """

    _instance: Optional["MetricsCollector"] = None
    _initialized: bool = False

    def __new__(cls, db_path: Path | None = None):
        """Implémente le pattern Singleton."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: Path | None = None):
        """Initialise le collector.

        Args:
            db_path: Chemin vers la base DuckDB. Si None, utilise DB_LLM_METRICS
        """
        if not self._initialized:
            self.db_path = db_path or DB_LLM_METRICS
            self._metrics: list[LLMCallMetrics] = []
            self._ensure_db_exists()
            MetricsCollector._initialized = True
            logger.info(f"MetricsCollector initialisé avec DB: {self.db_path}")

    def _ensure_db_exists(self) -> None:
        """Crée le répertoire et la table si nécessaire."""
        # Créer le répertoire
        DATA_LLM_METRICS_DIR.mkdir(parents=True, exist_ok=True)

        # Créer la table si elle n'existe pas
        with duckdb.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS llm_metrics (
                    timestamp TIMESTAMP,
                    provider VARCHAR,
                    model VARCHAR,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    total_tokens INTEGER,
                    latency_ms DOUBLE,
                    success BOOLEAN,
                    error_type VARCHAR,
                    cost_usd DOUBLE
                )
            """)
            logger.info("Table llm_metrics créée/vérifiée")

    def collect(self, metric: LLMCallMetrics) -> None:
        """Collecte une métrique.

        Args:
            metric: Métrique à collecter
        """
        self._metrics.append(metric)
        logger.debug(
            f"Métrique collectée: {metric.provider}/{metric.model} - "
            f"{metric.total_tokens} tokens - {metric.latency_ms:.0f}ms - "
            f"Success: {metric.success}"
        )

    def export_to_duckdb(self) -> None:
        """Exporte toutes les métriques collectées vers DuckDB."""
        if not self._metrics:
            logger.info("Aucune métrique à exporter")
            return

        with duckdb.connect(str(self.db_path)) as conn:
            # Convertir les métriques en liste de tuples
            data = [
                (
                    m.timestamp,
                    m.provider,
                    m.model,
                    m.prompt_tokens,
                    m.completion_tokens,
                    m.total_tokens,
                    m.latency_ms,
                    m.success,
                    m.error_type,
                    m.cost_usd,
                )
                for m in self._metrics
            ]

            # Insertion batch
            conn.executemany(
                """
                INSERT INTO llm_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                data,
            )

        logger.info(f"{len(self._metrics)} métriques exportées vers DuckDB")
        self._metrics.clear()

    def get_summary(self) -> dict:
        """Retourne un résumé des métriques stockées en DB.

        Returns:
            dict avec statistiques agrégées par provider
        """
        with duckdb.connect(str(self.db_path)) as conn:
            result = conn.execute("""
                SELECT
                    provider,
                    COUNT(*) as total_calls,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_calls,
                    SUM(prompt_tokens) as prompt_tokens,
                    SUM(completion_tokens) as completion_tokens,
                    SUM(total_tokens) as total_tokens,
                    AVG(latency_ms) as avg_latency_ms,
                    SUM(cost_usd) as total_cost_usd
                FROM llm_metrics
                GROUP BY provider
                ORDER BY provider
            """).fetchall()

            summary = {}
            for row in result:
                (
                    provider,
                    total,
                    success,
                    prompt_tok,
                    completion_tok,
                    total_tok,
                    latency,
                    cost,
                ) = row
                summary[provider] = {
                    "total_calls": total,
                    "successful_calls": success,
                    "error_rate": ((total - success) / total * 100 if total > 0 else 0),
                    "prompt_tokens": prompt_tok,
                    "completion_tokens": completion_tok,
                    "total_tokens": total_tok,
                    "avg_latency_ms": round(latency, 2) if latency else 0,
                    "total_cost_usd": round(cost, 4) if cost else 0,
                }

            return summary

    def clear_metrics(self) -> None:
        """Vide les métriques en mémoire (pas la DB)."""
        self._metrics.clear()
        logger.info("Métriques en mémoire vidées")

    def reset_db(self) -> None:
        """Supprime toutes les métriques de la DB (use with caution)."""
        with duckdb.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM llm_metrics")
        logger.warning("Toutes les métriques DB supprimées")


# Instance globale du collector
metrics_collector = MetricsCollector()
