"""Repository for class (classe) data."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

import duckdb

from src.storage.config import storage_settings
from src.storage.repositories.base import Repository


@dataclass
class Classe:
    """Class entity."""

    classe_id: str
    nom: str
    niveau: str | None = None
    annee_scolaire: str = "2024-2025"


class ClasseRepository(Repository[Classe]):
    """Repository for managing classes."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialize repository.

        Args:
            db_path: Path to database. Defaults to config setting.
        """
        self.db_path = Path(db_path) if db_path else storage_settings.db_path

    def _get_conn(self) -> duckdb.DuckDBPyConnection:
        """Get a new database connection."""
        return duckdb.connect(str(self.db_path))

    def create(self, classe: Classe) -> str:
        """Create a new class.

        Args:
            classe: Class to create.

        Returns:
            classe_id of created class.
        """
        if not classe.classe_id:
            classe.classe_id = str(uuid.uuid4())[:8]

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO classes (classe_id, nom, niveau, annee_scolaire)
                VALUES (?, ?, ?, ?)
                """,
                [classe.classe_id, classe.nom, classe.niveau, classe.annee_scolaire],
            )
        return classe.classe_id

    def get(self, classe_id: str) -> Classe | None:
        """Get a class by ID.

        Args:
            classe_id: Class identifier.

        Returns:
            Classe or None.
        """
        with self._get_conn() as conn:
            result = conn.execute(
                """
                SELECT classe_id, nom, niveau, annee_scolaire
                FROM classes
                WHERE classe_id = ?
                """,
                [classe_id],
            ).fetchone()

        if not result:
            return None
        return Classe(
            classe_id=result[0],
            nom=result[1],
            niveau=result[2],
            annee_scolaire=result[3],
        )

    def list(self, **filters) -> list[Classe]:
        """List classes with optional filters.

        Args:
            **filters: Optional filters (annee_scolaire, niveau).

        Returns:
            List of classes.
        """
        sql = "SELECT classe_id, nom, niveau, annee_scolaire FROM classes"
        conditions = []
        params = []

        if "annee_scolaire" in filters:
            conditions.append("annee_scolaire = ?")
            params.append(filters["annee_scolaire"])
        if "niveau" in filters:
            conditions.append("niveau = ?")
            params.append(filters["niveau"])

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += " ORDER BY nom"

        with self._get_conn() as conn:
            results = conn.execute(sql, params if params else None).fetchall()

        return [
            Classe(
                classe_id=row[0],
                nom=row[1],
                niveau=row[2],
                annee_scolaire=row[3],
            )
            for row in results
        ]

    def update(self, classe_id: str, **updates) -> bool:
        """Update a class.

        Args:
            classe_id: Class identifier.
            **updates: Fields to update (nom, niveau, annee_scolaire).

        Returns:
            True if updated.
        """
        if not updates:
            return False

        set_clauses = []
        params = []
        for key, value in updates.items():
            if key in ("nom", "niveau", "annee_scolaire"):
                set_clauses.append(f"{key} = ?")
                params.append(value)

        if not set_clauses:
            return False

        params.append(classe_id)
        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE classes SET {', '.join(set_clauses)} WHERE classe_id = ?",
                params,
            )
        return True

    def delete(self, classe_id: str) -> bool:
        """Delete a class.

        Args:
            classe_id: Class identifier.

        Returns:
            True if deleted.
        """
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM classes WHERE classe_id = ?",
                [classe_id],
            )
        return True

    def get_or_create(self, nom: str, niveau: str | None = None) -> Classe:
        """Get existing class by name or create new one.

        Args:
            nom: Class name.
            niveau: Optional level.

        Returns:
            Existing or newly created class.
        """
        with self._get_conn() as conn:
            result = conn.execute(
                "SELECT classe_id, nom, niveau, annee_scolaire FROM classes WHERE nom = ?",
                [nom],
            ).fetchone()

        if result:
            return Classe(
                classe_id=result[0],
                nom=result[1],
                niveau=result[2],
                annee_scolaire=result[3],
            )

        classe = Classe(
            classe_id=str(uuid.uuid4())[:8],
            nom=nom,
            niveau=niveau,
        )
        self.create(classe)
        return classe
