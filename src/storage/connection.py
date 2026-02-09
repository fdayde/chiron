"""DuckDB connection management.

Utilise une connexion persistante unique par fichier de base de données,
protégée par un threading.Lock pour la sécurité multi-thread (FastAPI
exécute les endpoints sync dans un thread pool).
"""

import atexit
import logging
import threading
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import duckdb

from src.core.exceptions import StorageError
from src.storage.config import storage_settings
from src.storage.schemas import INDEXES, MIGRATIONS, TABLE_ORDER, TABLES

logger = logging.getLogger(__name__)

# Verrou global et pool de connexions persistantes (une par fichier DB)
_db_lock = threading.Lock()
_connections: dict[str, duckdb.DuckDBPyConnection] = {}

_SHARED_CONNECTION: "DuckDBConnection | None" = None


class DuckDBConnection:
    """Gestion de connexion DuckDB avec connexion persistante thread-safe.

    Utilise une connexion unique par fichier DB, partagée entre toutes
    les instances (repositories). Un threading.Lock sérialise l'accès
    pour éviter les conflits de verrouillage fichier sous Windows.

    Usage:
        conn = DuckDBConnection()
        conn.ensure_tables()

        with conn._get_conn() as cur:
            result = cur.execute("SELECT * FROM eleves").fetchall()
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialise le gestionnaire de connexion.

        Args:
            db_path: Chemin vers la base. Par défaut: valeur de la config.
        """
        self.db_path = Path(db_path) if db_path else storage_settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _remove_wal_file(self) -> bool:
        """Remove corrupted WAL file to allow recovery.

        Returns:
            True if a WAL file was removed.
        """
        wal_path = Path(f"{self.db_path}.wal")
        if wal_path.exists():
            wal_path.unlink()
            logger.warning(
                "WAL corrompu supprime: %s "
                "(les dernieres transactions non committees sont perdues)",
                wal_path,
            )
            return True
        return False

    @contextmanager
    def _get_conn(self) -> Generator[duckdb.DuckDBPyConnection]:
        """Connexion persistante protégée par un lock.

        Crée la connexion au premier appel, puis la réutilise.
        Si le WAL est corrompu, le supprime et retente.
        Le lock est maintenu pendant toute la durée du bloc `with`.

        Yields:
            Connexion DuckDB partagée.
        """
        db_key = str(self.db_path)
        with _db_lock:
            if db_key not in _connections:
                try:
                    _connections[db_key] = duckdb.connect(db_key)
                except duckdb.InternalException:
                    # WAL corruption after crash — auto-repair
                    if self._remove_wal_file():
                        _connections[db_key] = duckdb.connect(db_key)
                    else:
                        raise
                logger.debug(f"Opened persistent connection: {db_key}")
            yield _connections[db_key]

    def ensure_tables(self) -> None:
        """Crée toutes les tables et index si ils n'existent pas."""
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

            for table_name in TABLE_ORDER:
                for idx_sql in INDEXES.get(table_name, []):
                    try:
                        conn.execute(idx_sql)
                        logger.debug(f"Ensured index for table: {table_name}")
                    except Exception as e:
                        raise StorageError(
                            f"Failed to create index for {table_name}: {e}"
                        ) from e

            # Run idempotent migrations for existing databases
            for migration_sql in MIGRATIONS:
                try:
                    conn.execute(migration_sql)
                except Exception as e:
                    logger.warning(f"Migration skipped: {e}")

        logger.info(f"Database initialized at {self.db_path}")


def get_connection() -> DuckDBConnection:
    """Retourne le gestionnaire de connexion partagé (singleton).

    Returns:
        Instance partagée de DuckDBConnection.
    """
    global _SHARED_CONNECTION
    if _SHARED_CONNECTION is None:
        _SHARED_CONNECTION = DuckDBConnection()
        _SHARED_CONNECTION.ensure_tables()
    return _SHARED_CONNECTION


@contextmanager
def managed_connection():
    """Context manager pour le cycle de vie de la connexion DB.

    Initialise la DB à l'entrée, ferme proprement à la sortie
    (flush WAL → fichier principal).

    Usage::

        with managed_connection():
            ui.run(...)
    """
    try:
        get_connection()
        yield
    finally:
        close_all_connections()


def close_all_connections() -> None:
    """Ferme proprement toutes les connexions DuckDB.

    Flush le WAL vers le fichier principal et libère les verrous.
    Appelé automatiquement via atexit à l'arrêt du process.
    """
    with _db_lock:
        for db_key, conn in _connections.items():
            try:
                conn.close()
                logger.info("Connexion DuckDB fermee: %s", db_key)
            except Exception:
                logger.warning("Erreur fermeture DuckDB: %s", db_key, exc_info=True)
        _connections.clear()


# Flush WAL on process exit (Ctrl+C, window close, etc.)
atexit.register(close_all_connections)


def reset_connection() -> None:
    """Réinitialise la connexion partagée (pour les tests)."""
    global _SHARED_CONNECTION
    _SHARED_CONNECTION = None
    close_all_connections()
