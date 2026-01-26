"""DuckDB connection management."""

import logging
from pathlib import Path

import duckdb

from src.core.exceptions import StorageError
from src.storage.config import storage_settings
from src.storage.schemas import TABLE_ORDER, TABLES

logger = logging.getLogger(__name__)

_SHARED_CONNECTION: "DuckDBConnection | None" = None


class DuckDBConnection:
    """Base class for DuckDB connection management.

    Utilise le context manager `with` pour chaque opération SQL,
    garantissant la fermeture automatique des connexions.

    Cette classe sert de base pour DuckDBRepository et peut être
    utilisée directement pour l'initialisation du schéma.

    Usage:
        conn = DuckDBConnection()
        conn.ensure_tables()

        # Avec context manager:
        with conn._get_conn() as cur:
            result = cur.execute("SELECT * FROM eleves").fetchall()
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialize connection manager.

        Args:
            db_path: Path to database file. Defaults to config setting.
        """
        self.db_path = Path(db_path) if db_path else storage_settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_conn(self) -> duckdb.DuckDBPyConnection:
        """Get a new connection for context manager usage.

        Returns:
            DuckDB connection that should be used with `with` statement.
        """
        return duckdb.connect(str(self.db_path))

    def ensure_tables(self) -> None:
        """Create all tables if they don't exist."""
        with self._get_conn() as conn:
            for table_name in TABLE_ORDER:
                sql = TABLES[table_name]
                try:
                    conn.execute(sql)
                    logger.debug(f"Ensured table: {table_name}")
                except Exception as e:
                    raise StorageError(
                        f"Failed to create table {table_name}: {e}"
                    ) from e

        logger.info(f"Database initialized at {self.db_path}")


def get_connection() -> DuckDBConnection:
    """Get shared database connection manager (singleton pattern).

    Returns:
        Shared DuckDBConnection instance.
    """
    global _SHARED_CONNECTION
    if _SHARED_CONNECTION is None:
        _SHARED_CONNECTION = DuckDBConnection()
        _SHARED_CONNECTION.ensure_tables()
    return _SHARED_CONNECTION


def reset_connection() -> None:
    """Reset the shared connection manager (for testing)."""
    global _SHARED_CONNECTION
    _SHARED_CONNECTION = None
