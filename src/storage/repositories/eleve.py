"""Repository for student (eleve) data."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

from src.core.models import EleveExtraction, MatiereExtraction
from src.storage.config import storage_settings
from src.storage.repositories.base import Repository


class EleveRepository(Repository[EleveExtraction]):
    """Repository for managing students."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialize repository.

        Args:
            db_path: Path to database. Defaults to config setting.
        """
        self.db_path = Path(db_path) if db_path else storage_settings.db_path

    def _get_conn(self) -> duckdb.DuckDBPyConnection:
        """Get a new database connection."""
        return duckdb.connect(str(self.db_path))

    def create(self, eleve: EleveExtraction) -> str:
        """Create a new student record.

        Args:
            eleve: Student data to store.

        Returns:
            eleve_id of created student.

        Raises:
            ValueError: If eleve_id is not set.
        """
        if not eleve.eleve_id:
            raise ValueError("eleve_id is required")

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO eleves (
                    eleve_id, classe_id, genre, trimestre,
                    absences_demi_journees, absences_justifiees, retards,
                    engagements, parcours, evenements, matieres
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    eleve.eleve_id,
                    eleve.classe,
                    eleve.genre,
                    eleve.trimestre,
                    eleve.absences_demi_journees,
                    eleve.absences_justifiees,
                    eleve.retards,
                    json.dumps(eleve.engagements),
                    json.dumps(eleve.parcours),
                    json.dumps(eleve.evenements),
                    json.dumps([m.model_dump() for m in eleve.matieres]),
                ],
            )
        return eleve.eleve_id

    def get(self, eleve_id: str) -> EleveExtraction | None:
        """Get a student by ID.

        Args:
            eleve_id: Student identifier.

        Returns:
            EleveExtraction or None.
        """
        with self._get_conn() as conn:
            result = conn.execute(
                """
                SELECT eleve_id, classe_id, genre, trimestre,
                       absences_demi_journees, absences_justifiees, retards,
                       engagements, parcours, evenements, matieres
                FROM eleves
                WHERE eleve_id = ?
                """,
                [eleve_id],
            ).fetchone()

        if not result:
            return None
        return self._row_to_eleve(result)

    def _row_to_eleve(self, row: tuple) -> EleveExtraction:
        """Convert database row to EleveExtraction."""
        matieres_data = json.loads(row[10]) if row[10] else []
        matieres = [MatiereExtraction(**m) for m in matieres_data]

        return EleveExtraction(
            eleve_id=row[0],
            classe=row[1],
            genre=row[2],
            trimestre=row[3],
            absences_demi_journees=row[4],
            absences_justifiees=row[5],
            retards=row[6],
            engagements=json.loads(row[7]) if row[7] else [],
            parcours=json.loads(row[8]) if row[8] else [],
            evenements=json.loads(row[9]) if row[9] else [],
            matieres=matieres,
        )

    def list(self, **filters) -> list[EleveExtraction]:
        """List students with optional filters.

        Args:
            **filters: Optional filters (classe_id, trimestre).

        Returns:
            List of students.
        """
        sql = """
            SELECT eleve_id, classe_id, genre, trimestre,
                   absences_demi_journees, absences_justifiees, retards,
                   engagements, parcours, evenements, matieres
            FROM eleves
        """
        conditions = []
        params = []

        if "classe_id" in filters:
            conditions.append("classe_id = ?")
            params.append(filters["classe_id"])
        if "trimestre" in filters:
            conditions.append("trimestre = ?")
            params.append(filters["trimestre"])

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += " ORDER BY eleve_id"

        with self._get_conn() as conn:
            results = conn.execute(sql, params if params else None).fetchall()

        return [self._row_to_eleve(row) for row in results]

    def get_by_classe(
        self, classe_id: str, trimestre: int | None = None
    ) -> list[EleveExtraction]:
        """Get all students in a class.

        Args:
            classe_id: Class identifier.
            trimestre: Optional trimester filter.

        Returns:
            List of students.
        """
        filters = {"classe_id": classe_id}
        if trimestre is not None:
            filters["trimestre"] = trimestre
        return self.list(**filters)

    def update(self, eleve_id: str, **updates) -> bool:
        """Update a student record.

        Args:
            eleve_id: Student identifier.
            **updates: Fields to update.

        Returns:
            True if updated.
        """
        if not updates:
            return False

        set_clauses = []
        params = []

        for key, value in updates.items():
            if key in (
                "genre",
                "trimestre",
                "absences_demi_journees",
                "absences_justifiees",
                "retards",
                "classe_id",
            ):
                set_clauses.append(f"{key} = ?")
                params.append(value)
            elif key in ("engagements", "parcours", "evenements"):
                set_clauses.append(f"{key} = ?")
                params.append(json.dumps(value))
            elif key == "matieres":
                set_clauses.append("matieres = ?")
                if (
                    isinstance(value, list)
                    and value
                    and hasattr(value[0], "model_dump")
                ):
                    params.append(json.dumps([m.model_dump() for m in value]))
                else:
                    params.append(json.dumps(value))

        if not set_clauses:
            return False

        params.append(eleve_id)
        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE eleves SET {', '.join(set_clauses)} WHERE eleve_id = ?",
                params,
            )
        return True

    def delete(self, eleve_id: str) -> bool:
        """Delete a student record.

        Args:
            eleve_id: Student identifier.

        Returns:
            True if deleted.
        """
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM eleves WHERE eleve_id = ?",
                [eleve_id],
            )
        return True

    def exists(self, eleve_id: str) -> bool:
        """Check if a student exists.

        Args:
            eleve_id: Student identifier.

        Returns:
            True if exists.
        """
        with self._get_conn() as conn:
            result = conn.execute(
                "SELECT 1 FROM eleves WHERE eleve_id = ?",
                [eleve_id],
            ).fetchone()
        return result is not None
