"""Storage module for DuckDB persistence."""

from src.storage.connection import DuckDBConnection, get_connection

__all__ = ["DuckDBConnection", "get_connection"]
