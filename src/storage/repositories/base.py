"""Base repository for DuckDB.

Architecture:
    DuckDBRepository[T] (ABC) - Base DuckDB avec code commun factorisé
        └── EleveRepository, SyntheseRepository, etc.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TypeVar

from src.storage.connection import DuckDBConnection

T = TypeVar("T")


class DuckDBRepository[T](DuckDBConnection, ABC):
    """Base DuckDB repository with common connection and query patterns.

    Factorise le code commun à tous les repositories DuckDB :
    - Gestion de la connexion (via DuckDBConnection._get_conn())
    - Pattern execute/fetch
    - Méthode exists()

    Les sous-classes doivent implémenter :
    - table_name (property)
    - id_column (property)
    - _row_to_entity() pour la conversion
    - create(), list(), update() pour la logique spécifique
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialize repository.

        Args:
            db_path: Path to database. Defaults to config setting.
        """
        super().__init__(db_path)

    @property
    @abstractmethod
    def table_name(self) -> str:
        """Nom de la table SQL."""
        ...

    @property
    @abstractmethod
    def id_column(self) -> str:
        """Nom de la colonne ID."""
        ...

    @abstractmethod
    def _row_to_entity(self, row: tuple) -> T:
        """Convertit une ligne SQL en entité.

        Args:
            row: Tuple de valeurs SQL.

        Returns:
            Entité typée.
        """
        ...

    # _get_conn() est hérité de DuckDBConnection

    def _execute(self, sql: str, params: list | None = None) -> list[tuple]:
        """Execute SQL and return results.

        Args:
            sql: SQL statement.
            params: Optional parameters.

        Returns:
            List of result tuples.
        """
        with self._get_conn() as conn:
            if params:
                return conn.execute(sql, params).fetchall()
            return conn.execute(sql).fetchall()

    def _execute_one(self, sql: str, params: list | None = None) -> tuple | None:
        """Execute SQL and return single result.

        Args:
            sql: SQL statement.
            params: Optional parameters.

        Returns:
            Single tuple or None.
        """
        results = self._execute(sql, params)
        return results[0] if results else None

    def _execute_write(self, sql: str, params: list | None = None) -> None:
        """Execute write SQL (INSERT, UPDATE, DELETE).

        Args:
            sql: SQL statement.
            params: Optional parameters.
        """
        with self._get_conn() as conn:
            if params:
                conn.execute(sql, params)
            else:
                conn.execute(sql)

    def exists(self, entity_id: str) -> bool:
        """Check if entity exists.

        Args:
            entity_id: Entity identifier.

        Returns:
            True if exists.
        """
        result = self._execute_one(
            f"SELECT 1 FROM {self.table_name} WHERE {self.id_column} = ?",
            [entity_id],
        )
        return result is not None

    def delete(self, entity_id: str) -> bool:
        """Delete an entity.

        Args:
            entity_id: Entity identifier.

        Returns:
            True if deleted.
        """
        self._execute_write(
            f"DELETE FROM {self.table_name} WHERE {self.id_column} = ?",
            [entity_id],
        )
        return True
