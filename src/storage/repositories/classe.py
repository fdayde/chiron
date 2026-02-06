"""Repository for class (classe) data."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from src.core.constants import get_current_school_year
from src.storage.repositories.base import DuckDBRepository


@dataclass
class Classe:
    """Class entity."""

    classe_id: str
    nom: str
    niveau: str | None = None
    etablissement: str | None = None
    annee_scolaire: str = field(default_factory=get_current_school_year)


class ClasseRepository(DuckDBRepository[Classe]):
    """Repository for managing classes."""

    @property
    def table_name(self) -> str:
        return "classes"

    @property
    def id_column(self) -> str:
        return "classe_id"

    def _row_to_entity(self, row: tuple) -> Classe:
        """Convert database row to Classe."""
        return Classe(
            classe_id=row[0],
            nom=row[1],
            niveau=row[2],
            etablissement=row[3] if len(row) > 3 else None,
            annee_scolaire=row[4] if len(row) > 4 else get_current_school_year(),
        )

    def create(self, classe: Classe) -> str:
        """Create a new class.

        Args:
            classe: Class to create.

        Returns:
            classe_id of created class.
        """
        if not classe.classe_id:
            classe.classe_id = str(uuid.uuid4())[:8]

        self._execute_write(
            """
            INSERT INTO classes (classe_id, nom, niveau, etablissement, annee_scolaire)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                classe.classe_id,
                classe.nom,
                classe.niveau,
                classe.etablissement,
                classe.annee_scolaire,
            ],
        )
        return classe.classe_id

    def get(self, classe_id: str) -> Classe | None:
        """Get a class by ID.

        Args:
            classe_id: Class identifier.

        Returns:
            Classe or None.
        """
        result = self._execute_one(
            """
            SELECT classe_id, nom, niveau, etablissement, annee_scolaire
            FROM classes
            WHERE classe_id = ?
            """,
            [classe_id],
        )
        if not result:
            return None
        return self._row_to_entity(result)

    def list(self, **filters) -> list[Classe]:
        """List classes with optional filters.

        Args:
            **filters: Optional filters (annee_scolaire, niveau).

        Returns:
            List of classes.
        """
        sql = (
            "SELECT classe_id, nom, niveau, etablissement, annee_scolaire FROM classes"
        )
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

        results = self._execute(sql, params if params else None)
        return [self._row_to_entity(row) for row in results]

    def update(self, classe_id: str, **updates) -> bool:
        """Update a class.

        Args:
            classe_id: Class identifier.
            **updates: Fields to update (nom, niveau, etablissement, annee_scolaire).

        Returns:
            True if updated.
        """
        if not updates:
            return False

        set_clauses = []
        params = []
        for key, value in updates.items():
            if key in ("nom", "niveau", "etablissement", "annee_scolaire"):
                set_clauses.append(f"{key} = ?")
                params.append(value)

        if not set_clauses:
            return False

        params.append(classe_id)
        self._execute_write(
            f"UPDATE classes SET {', '.join(set_clauses)} WHERE classe_id = ?",
            params,
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
        result = self._execute_one(
            "SELECT classe_id, nom, niveau, etablissement, annee_scolaire FROM classes WHERE nom = ?",
            [nom],
        )

        if result:
            return self._row_to_entity(result)

        classe = Classe(
            classe_id=str(uuid.uuid4())[:8],
            nom=nom,
            niveau=niveau,
        )
        self.create(classe)
        return classe
