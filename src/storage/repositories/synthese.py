"""Repository for synthesis (synthese) data."""

from __future__ import annotations

import json
import uuid

from src.core.models import Alerte, Reussite, SyntheseGeneree
from src.storage.repositories.base import DuckDBRepository


class SyntheseRepository(DuckDBRepository[SyntheseGeneree]):
    """Repository for managing generated syntheses."""

    @property
    def table_name(self) -> str:
        return "syntheses"

    @property
    def id_column(self) -> str:
        return "id"

    def _row_to_entity(self, row: tuple) -> SyntheseGeneree:
        """Convert database row to SyntheseGeneree.

        Expected row format (from SELECT synthese_texte, alertes_json, reussites_json,
        posture_generale, axes_travail_json):
            row[0]: synthese_texte
            row[1]: alertes_json
            row[2]: reussites_json
            row[3]: posture_generale
            row[4]: axes_travail_json
        """
        alertes_data = json.loads(row[1]) if row[1] else []
        reussites_data = json.loads(row[2]) if row[2] else []

        return SyntheseGeneree(
            synthese_texte=row[0],
            alertes=[Alerte(**a) for a in alertes_data],
            reussites=[Reussite(**r) for r in reussites_data],
            posture_generale=row[3],
            axes_travail=json.loads(row[4]) if row[4] else [],
        )

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
            metadata: Optional metadata with LLM details:
                - llm_provider: Provider name (openai, anthropic, mistral)
                - llm_model: Model used
                - llm_response_raw: Raw response text from LLM
                - prompt_template: Template name (e.g., "synthese_v1")
                - prompt_hash: Hash for traceability
                - tokens_input: Input tokens count
                - tokens_output: Output tokens count
                - tokens_total: Total tokens
                - llm_cost: Cost in USD
                - llm_duration_ms: Duration in milliseconds
                - llm_temperature: Temperature used
                - retry_count: Number of retries needed

        Returns:
            synthese_id of created record.
        """
        synthese_id = str(uuid.uuid4())[:8]
        metadata = metadata or {}

        self._execute_write(
            """
            INSERT INTO syntheses (
                id, eleve_id, trimestre, synthese_texte,
                llm_response_raw,
                alertes_json, reussites_json, posture_generale, axes_travail_json,
                status,
                llm_provider, llm_model,
                prompt_template, prompt_hash,
                tokens_input, tokens_output, tokens_total,
                llm_cost, llm_duration_ms, llm_temperature,
                retry_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                synthese_id,
                eleve_id,
                trimestre,
                synthese.synthese_texte,
                metadata.get("llm_response_raw"),
                json.dumps([a.model_dump() for a in synthese.alertes]),
                json.dumps([r.model_dump() for r in synthese.reussites]),
                synthese.posture_generale,
                json.dumps(synthese.axes_travail),
                "generated",
                metadata.get("llm_provider"),
                metadata.get("llm_model"),
                metadata.get("prompt_template"),
                metadata.get("prompt_hash"),
                metadata.get("tokens_input"),
                metadata.get("tokens_output"),
                metadata.get("tokens_total"),
                metadata.get("llm_cost"),
                metadata.get("llm_duration_ms"),
                metadata.get("llm_temperature"),
                metadata.get("retry_count", 0),
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
        result = self._execute_one(
            """
            SELECT synthese_texte, alertes_json, reussites_json,
                   posture_generale, axes_travail_json
            FROM syntheses
            WHERE id = ?
            """,
            [synthese_id],
        )
        if not result:
            return None
        return self._row_to_entity(result)

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
            SELECT synthese_texte, alertes_json, reussites_json,
                   posture_generale, axes_travail_json
            FROM syntheses
            WHERE eleve_id = ?
        """
        params = [eleve_id]

        if trimestre is not None:
            sql += " AND trimestre = ?"
            params.append(trimestre)

        sql += " ORDER BY created_at DESC LIMIT 1"

        result = self._execute_one(sql, params)
        if not result:
            return None
        return self._row_to_entity(result)

    def get_for_eleve_with_metadata(
        self, eleve_id: str, trimestre: int | None = None
    ) -> dict | None:
        """Get the latest synthesis for a student with id and status.

        Args:
            eleve_id: Student identifier.
            trimestre: Optional trimester filter.

        Returns:
            Dict with synthese_id, status, and synthese data, or None.
        """
        sql = """
            SELECT id, status, synthese_texte, alertes_json, reussites_json,
                   posture_generale, axes_travail_json
            FROM syntheses
            WHERE eleve_id = ?
        """
        params = [eleve_id]

        if trimestre is not None:
            sql += " AND trimestre = ?"
            params.append(trimestre)

        sql += " ORDER BY created_at DESC LIMIT 1"

        result = self._execute_one(sql, params)
        if not result:
            return None

        return {
            "synthese_id": result[0],
            "status": result[1],
            "synthese": self._row_to_entity(result[2:7]),
        }

    def delete_for_eleve(self, eleve_id: str, trimestre: int) -> int:
        """Delete existing syntheses for a student/trimester.

        Used before regeneration to avoid UNIQUE constraint violations.

        Args:
            eleve_id: Student identifier.
            trimestre: Trimester number.

        Returns:
            Number of deleted records.
        """
        result = self._execute_write(
            "DELETE FROM syntheses WHERE eleve_id = ? AND trimestre = ?",
            [eleve_id, trimestre],
        )
        return result.rowcount if hasattr(result, "rowcount") else 0

    def list(self, **filters) -> list[SyntheseGeneree]:
        """List syntheses with optional filters.

        Args:
            **filters: Optional filters (eleve_id, trimestre, status).

        Returns:
            List of syntheses.
        """
        sql = """
            SELECT synthese_texte, alertes_json, reussites_json,
                   posture_generale, axes_travail_json
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

        sql += " ORDER BY created_at DESC"

        results = self._execute(sql, params if params else None)
        return [self._row_to_entity(row) for row in results]

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

        set_clauses = ["updated_at = CURRENT_TIMESTAMP"]
        params = []

        if "synthese_texte" in updates:
            set_clauses.append("synthese_texte = ?")
            params.append(updates["synthese_texte"])
            set_clauses.append("edited_at = CURRENT_TIMESTAMP")
        if "status" in updates:
            set_clauses.append("status = ?")
            params.append(updates["status"])
        if "alertes" in updates:
            set_clauses.append("alertes_json = ?")
            alertes = updates["alertes"]
            if alertes and hasattr(alertes[0], "model_dump"):
                params.append(json.dumps([a.model_dump() for a in alertes]))
            else:
                params.append(json.dumps(alertes))
        if "reussites" in updates:
            set_clauses.append("reussites_json = ?")
            reussites = updates["reussites"]
            if reussites and hasattr(reussites[0], "model_dump"):
                params.append(json.dumps([r.model_dump() for r in reussites]))
            else:
                params.append(json.dumps(reussites))

        if len(set_clauses) == 1:  # Only updated_at
            return False

        params.append(synthese_id)
        self._execute_write(
            f"UPDATE syntheses SET {', '.join(set_clauses)} WHERE id = ?",
            params,
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
        if status == "validated":
            self._execute_write(
                """
                UPDATE syntheses
                SET status = ?, validated_at = CURRENT_TIMESTAMP,
                    validated_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                [status, validated_by, synthese_id],
            )
        else:
            self._execute_write(
                """
                UPDATE syntheses
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
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
            SELECT s.id, s.eleve_id, s.trimestre, s.status, s.created_at
            FROM syntheses s
            JOIN eleves e ON s.eleve_id = e.eleve_id
            WHERE s.status != 'validated'
        """
        params = []

        if classe_id:
            sql += " AND e.classe_id = ?"
            params.append(classe_id)

        sql += " ORDER BY s.created_at DESC"

        results = self._execute(sql, params if params else None)

        return [
            {
                "synthese_id": row[0],
                "eleve_id": row[1],
                "trimestre": row[2],
                "status": row[3],
                "created_at": row[4],
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
        results = self._execute(
            """
            SELECT s.id, s.eleve_id, s.synthese_texte,
                   s.alertes_json, s.reussites_json,
                   s.posture_generale, s.axes_travail_json,
                   s.validated_at, s.validated_by
            FROM syntheses s
            JOIN eleves e ON s.eleve_id = e.eleve_id
            WHERE s.status = 'validated'
              AND e.classe_id = ?
              AND s.trimestre = ?
            ORDER BY s.eleve_id
            """,
            [classe_id, trimestre],
        )

        return [
            {
                "synthese_id": row[0],
                "eleve_id": row[1],
                "synthese": self._row_to_entity(row[2:7]),
                "validated_at": row[7],
                "validated_by": row[8],
            }
            for row in results
        ]
