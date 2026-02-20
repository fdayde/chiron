"""Repository for synthesis (synthese) data."""

from __future__ import annotations

import json
import logging
import uuid

from src.core.models import Alerte, Reussite, SyntheseGeneree
from src.storage.repositories.base import DuckDBRepository

logger = logging.getLogger(__name__)


class SyntheseRepository(DuckDBRepository[SyntheseGeneree]):
    """Repository for managing generated syntheses."""

    @property
    def table_name(self) -> str:
        return "syntheses"

    @property
    def id_column(self) -> str:
        return "id"

    def _safe_json_loads(self, raw: str | None, field_name: str) -> list:
        """Parse JSON or return empty list on error."""
        if not raw:
            return []
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("JSON corrompu dans %s: %.100s", field_name, raw)
            return []

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
        alertes_data = self._safe_json_loads(row[1], "alertes_json")
        reussites_data = self._safe_json_loads(row[2], "reussites_json")

        return SyntheseGeneree(
            synthese_texte=row[0],
            alertes=[Alerte(**a) for a in alertes_data],
            reussites=[Reussite(**r) for r in reussites_data],
            posture_generale=row[3],
            axes_travail=self._safe_json_loads(row[4], "axes_travail_json"),
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
                - prompt_template: Template name (e.g., "synthese_v3")
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
        synthese_id = str(uuid.uuid4())[:12]
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
        rows = self._execute(
            "DELETE FROM syntheses WHERE eleve_id = ? AND trimestre = ? RETURNING 1",
            [eleve_id, trimestre],
        )
        return len(rows)

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
            JOIN eleves e ON s.eleve_id = e.eleve_id AND s.trimestre = e.trimestre
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
            JOIN eleves e ON s.eleve_id = e.eleve_id AND s.trimestre = e.trimestre
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

    def get_by_classe(self, classe_id: str, trimestre: int) -> dict[str, dict]:
        """Get all syntheses for a class indexed by eleve_id.

        Args:
            classe_id: Class identifier.
            trimestre: Trimester number.

        Returns:
            Dict mapping eleve_id to {synthese_id, status, synthese}.
        """
        results = self._execute(
            """
            SELECT s.id, s.eleve_id, s.status,
                   s.synthese_texte, s.alertes_json, s.reussites_json,
                   s.posture_generale, s.axes_travail_json
            FROM syntheses s
            JOIN eleves e ON s.eleve_id = e.eleve_id AND s.trimestre = e.trimestre
            WHERE e.classe_id = ? AND s.trimestre = ?
            ORDER BY s.eleve_id
            """,
            [classe_id, trimestre],
        )

        return {
            row[1]: {
                "synthese_id": row[0],
                "status": row[2],
                "synthese": self._row_to_entity(row[3:8]),
            }
            for row in results
        }

    def toggle_fewshot_example(self, synthese_id: str, is_example: bool) -> bool:
        """Toggle the few-shot example flag on a synthesis.

        Args:
            synthese_id: Synthesis identifier.
            is_example: Whether to mark as example.

        Returns:
            True if updated.
        """
        self._execute_write(
            """
            UPDATE syntheses
            SET is_fewshot_example = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            [is_example, synthese_id],
        )
        return True

    def count_fewshot_examples(self, classe_id: str, trimestre: int) -> int:
        """Count few-shot examples for a class/trimester.

        Args:
            classe_id: Class identifier.
            trimestre: Trimester number.

        Returns:
            Number of examples (0-3).
        """
        result = self._execute_one(
            """
            SELECT COUNT(*)
            FROM syntheses s
            JOIN eleves e ON s.eleve_id = e.eleve_id AND s.trimestre = e.trimestre
            WHERE e.classe_id = ? AND s.trimestre = ?
              AND s.is_fewshot_example = TRUE
              AND s.status = 'validated'
            """,
            [classe_id, trimestre],
        )
        return result[0] if result else 0

    def get_fewshot_examples(self, classe_id: str, trimestre: int) -> list[dict]:
        """Get few-shot examples for a class/trimester.

        Returns validated syntheses marked as examples, with student data.

        Args:
            classe_id: Class identifier.
            trimestre: Trimester number.

        Returns:
            List of dicts with eleve_id, synthese_texte, and eleve data fields.
        """
        results = self._execute(
            """
            SELECT s.eleve_id, s.synthese_texte,
                   e.genre, e.absences_demi_journees, e.absences_justifiees,
                   e.retards, e.engagements, e.matieres, e.moyenne_generale
            FROM syntheses s
            JOIN eleves e ON s.eleve_id = e.eleve_id AND s.trimestre = e.trimestre
            WHERE e.classe_id = ? AND s.trimestre = ?
              AND s.is_fewshot_example = TRUE
              AND s.status = 'validated'
            ORDER BY s.validated_at
            LIMIT 3
            """,
            [classe_id, trimestre],
        )

        return [
            {
                "eleve_id": row[0],
                "synthese_texte": row[1],
                "genre": row[2],
                "absences_demi_journees": row[3],
                "absences_justifiees": row[4],
                "retards": row[5],
                "engagements": row[6],
                "matieres": row[7],
                "moyenne_generale": row[8],
            }
            for row in results
        ]

    def is_fewshot_example(self, synthese_id: str) -> bool:
        """Check if a synthesis is marked as a few-shot example.

        Args:
            synthese_id: Synthesis identifier.

        Returns:
            True if marked as example.
        """
        result = self._execute_one(
            "SELECT is_fewshot_example FROM syntheses WHERE id = ?",
            [synthese_id],
        )
        return bool(result and result[0])

    def get_stats(self, classe_id: str, trimestre: int) -> dict:
        """Get aggregated statistics for a class and trimester.

        Args:
            classe_id: Class identifier.
            trimestre: Trimester number.

        Returns:
            Dict with aggregated stats (count, tokens, cost, etc.)
        """
        result = self._execute_one(
            """
            SELECT
                COUNT(*) as count,
                SUM(COALESCE(tokens_input, 0)) as total_tokens_input,
                SUM(COALESCE(tokens_output, 0)) as total_tokens_output,
                SUM(COALESCE(tokens_total, 0)) as total_tokens,
                SUM(COALESCE(llm_cost, 0)) as total_cost,
                COUNT(CASE WHEN status = 'validated' THEN 1 END) as validated_count,
                COUNT(CASE WHEN status = 'generated' THEN 1 END) as generated_count,
                COUNT(CASE WHEN status = 'edited' THEN 1 END) as edited_count
            FROM syntheses s
            JOIN eleves e ON s.eleve_id = e.eleve_id AND s.trimestre = e.trimestre
            WHERE e.classe_id = ? AND s.trimestre = ?
            """,
            [classe_id, trimestre],
        )

        if not result:
            return {
                "count": 0,
                "tokens_input": 0,
                "tokens_output": 0,
                "tokens_total": 0,
                "cost_usd": 0.0,
                "validated_count": 0,
                "generated_count": 0,
                "edited_count": 0,
            }

        return {
            "count": result[0] or 0,
            "tokens_input": result[1] or 0,
            "tokens_output": result[2] or 0,
            "tokens_total": result[3] or 0,
            "cost_usd": round(result[4] or 0, 4),
            "validated_count": result[5] or 0,
            "generated_count": result[6] or 0,
            "edited_count": result[7] or 0,
        }
