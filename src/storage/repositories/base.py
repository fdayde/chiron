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
        """Initialise le repository.

        Args:
            db_path: Chemin vers la base. Par défaut: valeur de la config.
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
        """Exécute du SQL et retourne les résultats.

        Args:
            sql: Requête SQL.
            params: Paramètres optionnels.

        Returns:
            Liste de tuples résultat.
        """
        with self._get_conn() as conn:
            if params:
                return conn.execute(sql, params).fetchall()
            return conn.execute(sql).fetchall()

    def _execute_one(self, sql: str, params: list | None = None) -> tuple | None:
        """Exécute du SQL et retourne un seul résultat.

        Args:
            sql: Requête SQL.
            params: Paramètres optionnels.

        Returns:
            Tuple unique ou None.
        """
        results = self._execute(sql, params)
        return results[0] if results else None

    def _execute_write(self, sql: str, params: list | None = None) -> None:
        """Exécute du SQL d'écriture (INSERT, UPDATE, DELETE).

        Args:
            sql: Requête SQL.
            params: Paramètres optionnels.
        """
        with self._get_conn() as conn:
            if params:
                conn.execute(sql, params)
            else:
                conn.execute(sql)

    def exists(self, entity_id: str) -> bool:
        """Vérifie si une entité existe.

        Args:
            entity_id: Identifiant de l'entité.

        Returns:
            True si elle existe.
        """
        result = self._execute_one(
            f"SELECT 1 FROM {self.table_name} WHERE {self.id_column} = ?",
            [entity_id],
        )
        return result is not None

    def delete(self, entity_id: str) -> bool:
        """Supprime une entité.

        Args:
            entity_id: Identifiant de l'entité.

        Returns:
            True si supprimée.
        """
        self._execute_write(
            f"DELETE FROM {self.table_name} WHERE {self.id_column} = ?",
            [entity_id],
        )
        return True
