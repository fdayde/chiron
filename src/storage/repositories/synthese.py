"""Repository for synthesis (synthese) data."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import duckdb

from src.core.models import Alerte, Reussite, SyntheseGeneree
from src.storage.config import storage_settings
from src.storage.repositories.base import Repository


class SyntheseRepository(Repository[SyntheseGeneree]):
    """Repository for managing generated syntheses."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialize repository.

        Args:
            db_path: Path to database. Defaults to config setting.
        """
        self.db_path = Path(db_path) if db_path else storage_settings.db_path

    def _get_conn(self) -> duckdb.DuckDBPyConnection:
        """Get a new database connection."""
        return duckdb.connect(str(self.db_path))

    def create(
        self,
        eleve_id: str,
        synthese: SyntheseGeneree,
        trimestre: int,
        metadata: dict | None = None,
    ) -> str:
        """Create a new synthesis record.

        Args:
            eleve_id: Student identifier.
            synthese: Generated synthesis.
            trimestre: Trimester number.
            metadata: Optional metadata (provider, model, tokens_used).

        Returns:
            synthese_id of created record.
        """
        synthese_id = str(uuid.uuid4())[:8]
        metadata = metadata or {}

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO syntheses (
                    synthese_id, eleve_id, trimestre, synthese_texte,
                    alertes, reussites, posture_generale, axes_travail,
                    status, provider, model, tokens_used
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    synthese_id,
                    eleve_id,
                    trimestre,
                    synthese.synthese_texte,
                    json.dumps([a.model_dump() for a in synthese.alertes]),
                    json.dumps([r.model_dump() for r in synthese.reussites]),
                    synthese.posture_generale,
                    json.dumps(synthese.axes_travail),
                    "generated",
                    metadata.get("provider"),
                    metadata.get("model"),
                    metadata.get("tokens_used"),
                ],
            )
        return synthese_id

    def get(self, synthese_id: str) -> SyntheseGeneree | None:
        """Get a synthesis by ID.

        Args:
            synthese_id: Synthesis identifier.

        Returns:
            SyntheseGeneree or None.
        """
        with self._get_conn() as conn:
            result = conn.execute(
                """
                SELECT synthese_texte, alertes, reussites, posture_generale, axes_travail
                FROM syntheses
                WHERE synthese_id = ?
                """,
                [synthese_id],
            ).fetchone()

        if not result:
            return None
        return self._row_to_synthese(result)

    def _row_to_synthese(self, row: tuple) -> SyntheseGeneree:
        """Convert database row to SyntheseGeneree."""
        alertes_data = json.loads(row[1]) if row[1] else []
        reussites_data = json.loads(row[2]) if row[2] else []

        return SyntheseGeneree(
            synthese_texte=row[0],
            alertes=[Alerte(**a) for a in alertes_data],
            reussites=[Reussite(**r) for r in reussites_data],
            posture_generale=row[3],
            axes_travail=json.loads(row[4]) if row[4] else [],
        )

    def get_for_eleve(
        self, eleve_id: str, trimestre: int | None = None
    ) -> SyntheseGeneree | None:
        """Get the latest synthesis for a student.

        Args:
            eleve_id: Student identifier.
            trimestre: Optional trimester filter.

        Returns:
            Latest SyntheseGeneree or None.
        """
        sql = """
            SELECT synthese_texte, alertes, reussites, posture_generale, axes_travail
            FROM syntheses
            WHERE eleve_id = ?
        """
        params = [eleve_id]

        if trimestre is not None:
            sql += " AND trimestre = ?"
            params.append(trimestre)

        sql += " ORDER BY generated_at DESC LIMIT 1"

        with self._get_conn() as conn:
            result = conn.execute(sql, params).fetchone()

        if not result:
            return None
        return self._row_to_synthese(result)

    def list(self, **filters) -> list[SyntheseGeneree]:
        """List syntheses with optional filters.

        Args:
            **filters: Optional filters (eleve_id, trimestre, status).

        Returns:
            List of syntheses.
        """
        sql = """
            SELECT synthese_texte, alertes, reussites, posture_generale, axes_travail
            FROM syntheses
        """
        conditions = []
        params = []

        for key in ("eleve_id", "trimestre", "status"):
            if key in filters:
                conditions.append(f"{key} = ?")
                params.append(filters[key])

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += " ORDER BY generated_at DESC"

        with self._get_conn() as conn:
            results = conn.execute(sql, params if params else None).fetchall()

        return [self._row_to_synthese(row) for row in results]

    def update(self, synthese_id: str, **updates) -> bool:
        """Update a synthesis record.

        Args:
            synthese_id: Synthesis identifier.
            **updates: Fields to update.

        Returns:
            True if updated.
        """
        if not updates:
            return False

        set_clauses = []
        params = []

        if "synthese_texte" in updates:
            set_clauses.append("synthese_texte = ?")
            params.append(updates["synthese_texte"])
        if "status" in updates:
            set_clauses.append("status = ?")
            params.append(updates["status"])
        if "alertes" in updates:
            set_clauses.append("alertes = ?")
            alertes = updates["alertes"]
            if alertes and hasattr(alertes[0], "model_dump"):
                params.append(json.dumps([a.model_dump() for a in alertes]))
            else:
                params.append(json.dumps(alertes))
        if "reussites" in updates:
            set_clauses.append("reussites = ?")
            reussites = updates["reussites"]
            if reussites and hasattr(reussites[0], "model_dump"):
                params.append(json.dumps([r.model_dump() for r in reussites]))
            else:
                params.append(json.dumps(reussites))

        if not set_clauses:
            return False

        params.append(synthese_id)
        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE syntheses SET {', '.join(set_clauses)} WHERE synthese_id = ?",
                params,
            )
        return True

    def delete(self, synthese_id: str) -> bool:
        """Delete a synthesis record.

        Args:
            synthese_id: Synthesis identifier.

        Returns:
            True if deleted.
        """
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM syntheses WHERE synthese_id = ?",
                [synthese_id],
            )
        return True

    def update_status(
        self,
        synthese_id: str,
        status: str,
        validated_by: str | None = None,
    ) -> bool:
        """Update synthesis status.

        Args:
            synthese_id: Synthesis identifier.
            status: New status (generated, edited, validated).
            validated_by: Optional validator name.

        Returns:
            True if updated.
        """
        with self._get_conn() as conn:
            if status == "validated":
                conn.execute(
                    """
                    UPDATE syntheses
                    SET status = ?, validated_at = CURRENT_TIMESTAMP, validated_by = ?
                    WHERE synthese_id = ?
                    """,
                    [status, validated_by, synthese_id],
                )
            else:
                conn.execute(
                    "UPDATE syntheses SET status = ? WHERE synthese_id = ?",
                    [status, synthese_id],
                )
        return True

    def get_pending(self, classe_id: str | None = None) -> list[dict]:
        """Get syntheses pending validation.

        Args:
            classe_id: Optional class filter.

        Returns:
            List of pending syntheses with metadata.
        """
        sql = """
            SELECT s.synthese_id, s.eleve_id, s.trimestre, s.status, s.generated_at
            FROM syntheses s
            JOIN eleves e ON s.eleve_id = e.eleve_id
            WHERE s.status != 'validated'
        """
        params = []

        if classe_id:
            sql += " AND e.classe_id = ?"
            params.append(classe_id)

        sql += " ORDER BY s.generated_at DESC"

        with self._get_conn() as conn:
            results = conn.execute(sql, params if params else None).fetchall()

        return [
            {
                "synthese_id": row[0],
                "eleve_id": row[1],
                "trimestre": row[2],
                "status": row[3],
                "generated_at": row[4],
            }
            for row in results
        ]

    def get_validated(self, classe_id: str, trimestre: int) -> list[dict]:
        """Get validated syntheses for a class and trimester.

        Args:
            classe_id: Class identifier.
            trimestre: Trimester number.

        Returns:
            List of validated syntheses with full data.
        """
        with self._get_conn() as conn:
            results = conn.execute(
                """
                SELECT s.synthese_id, s.eleve_id, s.synthese_texte,
                       s.alertes, s.reussites, s.posture_generale, s.axes_travail,
                       s.validated_at, s.validated_by
                FROM syntheses s
                JOIN eleves e ON s.eleve_id = e.eleve_id
                WHERE s.status = 'validated'
                  AND e.classe_id = ?
                  AND s.trimestre = ?
                ORDER BY s.eleve_id
                """,
                [classe_id, trimestre],
            ).fetchall()

        return [
            {
                "synthese_id": row[0],
                "eleve_id": row[1],
                "synthese": self._row_to_synthese(row[2:7]),
                "validated_at": row[7],
                "validated_by": row[8],
            }
            for row in results
        ]
