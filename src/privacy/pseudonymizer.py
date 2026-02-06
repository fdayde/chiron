"""Pseudonymizer for RGPD-compliant student data handling.

Replaces real names with pseudonyms and maintains a secure mapping
in DuckDB for later depseudonymization when needed.
"""

import logging
import re
import threading
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import duckdb

from src.core.exceptions import PrivacyError
from src.privacy.config import privacy_settings

logger = logging.getLogger(__name__)


class Pseudonymizer:
    """Handles pseudonymization of student data.

    Creates pseudo IDs and stores the mapping in DuckDB
    for secure depseudonymization.

    Usage:
        pseudo = Pseudonymizer()
        eleve_id = pseudo.create_eleve_id("Dupont", "Marie", "5A")
        # eleve_id = "ELEVE_001"

        # Later, to recover original data:
        original = pseudo.depseudonymize("ELEVE_001")
    """

    _lock = threading.Lock()
    _conn: duckdb.DuckDBPyConnection | None = None

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialize pseudonymizer.

        Args:
            db_path: Path to DuckDB database. Defaults to config setting.
        """
        self.db_path = Path(db_path) if db_path else Path(privacy_settings.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_table()

    @contextmanager
    def _get_connection(self) -> Generator[duckdb.DuckDBPyConnection]:
        """Connexion persistante protégée par un lock.

        Yields:
            Connexion DuckDB partagée.
        """
        with self._lock:
            if Pseudonymizer._conn is None:
                Pseudonymizer._conn = duckdb.connect(str(self.db_path))
            yield Pseudonymizer._conn

    def _ensure_table(self) -> None:
        """Ensure the mapping table exists with proper constraints."""
        with self._get_connection() as conn:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {privacy_settings.mapping_table} (
                    eleve_id VARCHAR PRIMARY KEY,
                    nom_original VARCHAR NOT NULL,
                    prenom_original VARCHAR,
                    classe_id VARCHAR NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(nom_original, prenom_original, classe_id)
                )
            """)
            # Add unique constraint if table already exists (migration)
            try:
                conn.execute(f"""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_eleve_identity
                    ON {privacy_settings.mapping_table} (nom_original, prenom_original, classe_id)
                """)
            except duckdb.CatalogException:
                pass  # Index already exists

    def create_eleve_id(
        self,
        nom: str,
        prenom: str | None,
        classe_id: str,
    ) -> str:
        """Crée un eleve_id et stocke le mapping nom/prenom -> eleve_id.

        Idempotent: retourne l'ID existant si le mapping existe déjà.

        Args:
            nom: Nom de famille de l'élève.
            prenom: Prénom de l'élève (optionnel).
            classe_id: Identifiant de la classe.

        Returns:
            eleve_id généré ou existant (ex: "ELEVE_001").

        Raises:
            PrivacyError: Si le nom est vide ou si la génération échoue.
        """
        if not nom:
            raise PrivacyError("Cannot create eleve_id: nom is required")

        # Check if mapping already exists (idempotent)
        existing = self._get_existing_mapping(nom, prenom, classe_id)
        if existing:
            logger.info(f"Found existing mapping for {nom} -> {existing}")
            return existing

        # Generate new eleve_id and store mapping
        eleve_id = self._generate_eleve_id_atomic(classe_id, nom, prenom)
        logger.info(f"Created mapping: {nom} {prenom or ''} -> {eleve_id}")
        return eleve_id

    def _get_existing_mapping(
        self, nom: str, prenom: str | None, classe_id: str
    ) -> str | None:
        """Check if a mapping already exists for this student.

        Args:
            nom: Student's last name.
            prenom: Student's first name (may be None).
            classe_id: Class identifier.

        Returns:
            Existing eleve_id if found, None otherwise.
        """
        with self._get_connection() as conn:
            if prenom:
                result = conn.execute(
                    f"""
                    SELECT eleve_id FROM {privacy_settings.mapping_table}
                    WHERE nom_original = ? AND prenom_original = ? AND classe_id = ?
                    """,
                    [nom, prenom, classe_id],
                ).fetchone()
            else:
                result = conn.execute(
                    f"""
                    SELECT eleve_id FROM {privacy_settings.mapping_table}
                    WHERE nom_original = ? AND prenom_original IS NULL AND classe_id = ?
                    """,
                    [nom, classe_id],
                ).fetchone()
        return result[0] if result else None

    def _generate_eleve_id_atomic(
        self, classe_id: str, nom: str, prenom: str | None
    ) -> str:
        """Generate a unique eleve_id atomically using INSERT with retry.

        Args:
            classe_id: Class identifier.
            nom: Student's last name.
            prenom: Student's first name.

        Returns:
            Generated eleve_id.

        Raises:
            PrivacyError: If ID generation fails after retries.
        """
        max_retries = 10
        for _attempt in range(max_retries):
            eleve_id = self._generate_eleve_id(classe_id)

            try:
                with self._get_connection() as conn:
                    conn.execute(
                        f"""
                        INSERT INTO {privacy_settings.mapping_table}
                        (eleve_id, nom_original, prenom_original, classe_id)
                        VALUES (?, ?, ?, ?)
                        """,
                        [eleve_id, nom, prenom, classe_id],
                    )
                return eleve_id
            except Exception as e:
                error_str = str(e).lower()
                if "unique" in error_str or "duplicate" in error_str:
                    # Either eleve_id or (nom, prenom, classe_id) conflict
                    # Check if it's a duplicate student
                    existing = self._get_existing_mapping(nom, prenom, classe_id)
                    if existing:
                        return existing
                    # Otherwise, retry with a new ID
                    continue
                raise PrivacyError(f"Failed to store mapping: {e}") from e

        raise PrivacyError(
            f"Failed to generate unique eleve_id after {max_retries} attempts"
        )

    def _generate_eleve_id(self, classe_id: str) -> str:
        """Generate a unique eleve_id.

        Args:
            classe_id: Class identifier.

        Returns:
            Unique eleve_id like "ELEVE_001".
        """
        with self._get_connection() as conn:
            result = conn.execute(
                f"""
                SELECT COUNT(*) FROM {privacy_settings.mapping_table}
                WHERE classe_id = ?
                """,
                [classe_id],
            ).fetchone()
            count = result[0] if result else 0

        return f"{privacy_settings.pseudonym_prefix}{count + 1:03d}"

    def depseudonymize(self, eleve_id: str) -> dict | None:
        """Retrieve original identity for an eleve_id.

        Args:
            eleve_id: Pseudonymized identifier.

        Returns:
            Dict with nom_original, prenom_original, classe_id or None.
        """
        with self._get_connection() as conn:
            result = conn.execute(
                f"""
                SELECT nom_original, prenom_original, classe_id
                FROM {privacy_settings.mapping_table}
                WHERE eleve_id = ?
                """,
                [eleve_id],
            ).fetchone()

        if not result:
            return None

        return {
            "nom_original": result[0],
            "prenom_original": result[1],
            "classe_id": result[2],
        }

    def pseudonymize_text(self, text: str, classe_id: str) -> str:
        """Replace all known names in a text with their pseudonyms.

        Args:
            text: Text potentially containing student names.
            classe_id: Class to look up names from.

        Returns:
            Text with names replaced by pseudonyms.
        """
        with self._get_connection() as conn:
            mappings = conn.execute(
                f"""
                SELECT eleve_id, nom_original, prenom_original
                FROM {privacy_settings.mapping_table}
                WHERE classe_id = ?
                """,
                [classe_id],
            ).fetchall()

        for eleve_id, nom, prenom in mappings:
            if nom:
                # Replace full name (case insensitive)
                if prenom:
                    pattern = re.compile(
                        rf"\b{re.escape(prenom)}\s+{re.escape(nom)}\b",
                        re.IGNORECASE,
                    )
                    text = pattern.sub(eleve_id, text)
                    pattern = re.compile(
                        rf"\b{re.escape(nom)}\s+{re.escape(prenom)}\b",
                        re.IGNORECASE,
                    )
                    text = pattern.sub(eleve_id, text)
                # Replace just nom
                pattern = re.compile(rf"\b{re.escape(nom)}\b", re.IGNORECASE)
                text = pattern.sub(eleve_id, text)

        return text

    def depseudonymize_text(self, text: str, classe_id: str | None = None) -> str:
        """Restore original names in a text.

        Args:
            text: Text containing pseudonyms.
            classe_id: Optional class filter to scope depseudonymization.
                       Recommended for security to avoid cross-class data leaks.

        Returns:
            Text with pseudonyms replaced by original names.
        """
        with self._get_connection() as conn:
            if classe_id:
                mappings = conn.execute(
                    f"""
                    SELECT eleve_id, nom_original, prenom_original
                    FROM {privacy_settings.mapping_table}
                    WHERE classe_id = ?
                    """,
                    [classe_id],
                ).fetchall()
            else:
                mappings = conn.execute(
                    f"""
                    SELECT eleve_id, nom_original, prenom_original
                    FROM {privacy_settings.mapping_table}
                    """,
                ).fetchall()

        for eleve_id, nom, prenom in mappings:
            if nom:
                replacement = prenom if prenom else nom
                text = text.replace(eleve_id, replacement)

        return text

    def list_mappings(self, classe_id: str | None = None) -> list[dict]:
        """List all pseudonymization mappings.

        Args:
            classe_id: Optional filter by class.

        Returns:
            List of mapping dictionaries.
        """
        with self._get_connection() as conn:
            if classe_id:
                result = conn.execute(
                    f"""
                    SELECT eleve_id, nom_original, prenom_original, classe_id, created_at
                    FROM {privacy_settings.mapping_table}
                    WHERE classe_id = ?
                    ORDER BY created_at
                    """,
                    [classe_id],
                ).fetchall()
            else:
                result = conn.execute(
                    f"""
                    SELECT eleve_id, nom_original, prenom_original, classe_id, created_at
                    FROM {privacy_settings.mapping_table}
                    ORDER BY created_at
                    """,
                ).fetchall()

        return [
            {
                "eleve_id": row[0],
                "nom_original": row[1],
                "prenom_original": row[2],
                "classe_id": row[3],
                "created_at": row[4],
            }
            for row in result
        ]

    def clear_mappings(self, classe_id: str | None = None) -> int:
        """Clear pseudonymization mappings.

        Args:
            classe_id: Optional filter to clear only one class.

        Returns:
            Number of mappings deleted.
        """
        with self._get_connection() as conn:
            if classe_id:
                result = conn.execute(
                    f"""
                    DELETE FROM {privacy_settings.mapping_table}
                    WHERE classe_id = ?
                    """,
                    [classe_id],
                )
            else:
                result = conn.execute(f"DELETE FROM {privacy_settings.mapping_table}")
            return result.rowcount
