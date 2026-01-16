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
    """Managed DuckDB connection with schema initialization.

    Supports context manager for automatic connection handling.

    Usage:
        conn = DuckDBConnection()
        conn.ensure_tables()

        # Using context manager (recommended):
        with conn.cursor() as cur:
            result = cur.execute("SELECT * FROM eleves").fetchall()

        # Direct execute (also supported):
        result = conn.execute("SELECT * FROM eleves")
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialize connection.

        Args:
            db_path: Path to database file. Defaults to config setting.
        """
        self.db_path = Path(db_path) if db_path else storage_settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: duckdb.DuckDBPyConnection | None = None

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        """Get or create connection."""
        if self._conn is None:
            self._conn = duckdb.connect(str(self.db_path))
        return self._conn

    def cursor(self) -> duckdb.DuckDBPyConnection:
        """Get a cursor for context manager usage.

        Returns:
            DuckDB connection that can be used as context manager.
        """
        return duckdb.connect(str(self.db_path))

    def execute(self, sql: str, params: list | tuple | None = None) -> list[tuple]:
        """Execute SQL and return results.

        Args:
            sql: SQL statement.
            params: Optional parameters.

        Returns:
            List of result tuples.
        """
        try:
            if params:
                result = self.conn.execute(sql, params)
            else:
                result = self.conn.execute(sql)
            return result.fetchall()
        except Exception as e:
            raise StorageError(f"SQL execution failed: {e}") from e

    def execute_returning(
        self, sql: str, params: list | tuple | None = None
    ) -> tuple | None:
        """Execute SQL and return single row.

        Args:
            sql: SQL statement.
            params: Optional parameters.

        Returns:
            Single result tuple or None.
        """
        results = self.execute(sql, params)
        return results[0] if results else None

    def executemany(self, sql: str, params_list: list[list | tuple]) -> None:
        """Execute SQL with multiple parameter sets.

        Args:
            sql: SQL statement.
            params_list: List of parameter tuples.
        """
        try:
            self.conn.executemany(sql, params_list)
        except Exception as e:
            raise StorageError(f"SQL executemany failed: {e}") from e

    def ensure_tables(self) -> None:
        """Create all tables if they don't exist."""
        for table_name in TABLE_ORDER:
            sql = TABLES[table_name]
            try:
                self.conn.execute(sql)
                logger.debug(f"Ensured table: {table_name}")
            except Exception as e:
                raise StorageError(f"Failed to create table {table_name}: {e}") from e

        logger.info(f"Database initialized at {self.db_path}")

    def close(self) -> None:
        """Close the connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None


def get_connection() -> DuckDBConnection:
    """Get shared database connection (singleton pattern).

    Returns:
        Shared DuckDBConnection instance.
    """
    global _SHARED_CONNECTION
    if _SHARED_CONNECTION is None:
        _SHARED_CONNECTION = DuckDBConnection()
        _SHARED_CONNECTION.ensure_tables()
    return _SHARED_CONNECTION


def reset_connection() -> None:
    """Reset the shared connection (for testing)."""
    global _SHARED_CONNECTION
    if _SHARED_CONNECTION is not None:
        _SHARED_CONNECTION.close()
        _SHARED_CONNECTION = None
