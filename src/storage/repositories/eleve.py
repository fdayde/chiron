"""Repository des élèves.

Gère le stockage des données élèves avec clé composite (eleve_id, trimestre).
Un même élève peut avoir plusieurs enregistrements, un par trimestre.
"""

from __future__ import annotations

import json
import logging

from src.core.models import EleveExtraction, MatiereExtraction
from src.storage.repositories.base import DuckDBRepository

logger = logging.getLogger(__name__)


class EleveRepository(DuckDBRepository[EleveExtraction]):
    """Repository pour la gestion des élèves.

    Note : La clé primaire est (eleve_id, trimestre), pas eleve_id seul.
    Utiliser exists(eleve_id, trimestre) pour vérifier l'existence.
    """

    @property
    def table_name(self) -> str:
        return "eleves"

    @property
    def id_column(self) -> str:
        return "eleve_id"

    def _row_to_entity(self, row: tuple) -> EleveExtraction:
        """Convertit une ligne SQL en EleveExtraction.

        Format attendu du SELECT :
            0: eleve_id, 1: classe_id, 2: trimestre,
            3: raw_text, 4: moyenne_generale,
            5: genre, 6: absences_demi_journees, 7: absences_justifiees, 8: retards,
            9: engagements, 10: parcours, 11: evenements, 12: matieres

        Gère le JSON corrompu en loggant un warning et retournant des valeurs par défaut.
        """
        eleve_id = row[0]

        # Parse matieres with error handling
        matieres = []
        try:
            matieres_data = json.loads(row[12]) if row[12] else []
            matieres = [MatiereExtraction(**m) for m in matieres_data]
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(f"Failed to parse matieres for {eleve_id}: {e}")

        # Parse other JSON fields with error handling
        def safe_json_loads(data: str | None, field_name: str) -> list:
            if not data:
                return []
            try:
                return json.loads(data)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse {field_name} for {eleve_id}: {e}")
                return []

        return EleveExtraction(
            eleve_id=eleve_id,
            classe=row[1],
            trimestre=row[2],
            raw_text=row[3],
            moyenne_generale=row[4],
            genre=row[5],
            absences_demi_journees=row[6],
            absences_justifiees=row[7],
            retards=row[8],
            engagements=safe_json_loads(row[9], "engagements"),
            parcours=safe_json_loads(row[10], "parcours"),
            evenements=safe_json_loads(row[11], "evenements"),
            matieres=matieres,
        )

    def create(self, eleve: EleveExtraction) -> str:
        """Crée un enregistrement élève pour un trimestre donné.

        Args:
            eleve: Données de l'élève (eleve_id et trimestre requis).

        Returns:
            eleve_id de l'élève créé.

        Raises:
            ValueError: Si eleve_id ou trimestre manquant.
        """
        if not eleve.eleve_id:
            raise ValueError("eleve_id is required")
        if eleve.trimestre is None:
            raise ValueError("trimestre is required")

        self._execute_write(
            """
            INSERT INTO eleves (
                eleve_id, classe_id, trimestre,
                raw_text, moyenne_generale,
                genre, absences_demi_journees, absences_justifiees, retards,
                engagements, parcours, evenements, matieres
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                eleve.eleve_id,
                eleve.classe,
                eleve.trimestre,
                eleve.raw_text,
                eleve.moyenne_generale,
                eleve.genre,
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

    def get(
        self, eleve_id: str, trimestre: int | None = None
    ) -> EleveExtraction | None:
        """Récupère un élève par ID et optionnellement par trimestre.

        Args:
            eleve_id: Identifiant de l'élève.
            trimestre: Numéro du trimestre. Si None, retourne le plus récent.

        Returns:
            EleveExtraction ou None.
        """
        if trimestre is not None:
            result = self._execute_one(
                """
                SELECT eleve_id, classe_id, trimestre,
                       raw_text, moyenne_generale,
                       genre, absences_demi_journees, absences_justifiees, retards,
                       engagements, parcours, evenements, matieres
                FROM eleves
                WHERE eleve_id = ? AND trimestre = ?
                """,
                [eleve_id, trimestre],
            )
        else:
            # Return the latest trimester
            result = self._execute_one(
                """
                SELECT eleve_id, classe_id, trimestre,
                       raw_text, moyenne_generale,
                       genre, absences_demi_journees, absences_justifiees, retards,
                       engagements, parcours, evenements, matieres
                FROM eleves
                WHERE eleve_id = ?
                ORDER BY trimestre DESC
                LIMIT 1
                """,
                [eleve_id],
            )
        if not result:
            return None
        return self._row_to_entity(result)

    def exists(self, eleve_id: str, trimestre: int | None = None) -> bool:
        """Vérifie si un enregistrement élève existe.

        Args:
            eleve_id: Identifiant de l'élève.
            trimestre: Numéro du trimestre. Si None, vérifie tout trimestre.

        Returns:
            True si l'enregistrement existe.
        """
        if trimestre is not None:
            result = self._execute_one(
                "SELECT 1 FROM eleves WHERE eleve_id = ? AND trimestre = ?",
                [eleve_id, trimestre],
            )
        else:
            result = self._execute_one(
                "SELECT 1 FROM eleves WHERE eleve_id = ?",
                [eleve_id],
            )
        return result is not None

    def list(self, **filters) -> list[EleveExtraction]:
        """Liste les élèves avec filtres optionnels.

        Args:
            **filters: Filtres optionnels (classe_id, trimestre).

        Returns:
            Liste d'élèves.
        """
        sql = """
            SELECT eleve_id, classe_id, trimestre,
                   raw_text, moyenne_generale,
                   genre, absences_demi_journees, absences_justifiees, retards,
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

        sql += " ORDER BY eleve_id, trimestre"

        results = self._execute(sql, params if params else None)
        return [self._row_to_entity(row) for row in results]

    def get_by_classe(
        self, classe_id: str, trimestre: int | None = None
    ) -> list[EleveExtraction]:
        """Récupère tous les élèves d'une classe.

        Args:
            classe_id: Identifiant de la classe.
            trimestre: Filtre trimestre optionnel.

        Returns:
            Liste d'élèves.
        """
        filters = {"classe_id": classe_id}
        if trimestre is not None:
            filters["trimestre"] = trimestre
        return self.list(**filters)

    def update(self, eleve_id: str, trimestre: int, **updates) -> bool:
        """Met à jour un enregistrement élève.

        Args:
            eleve_id: Identifiant de l'élève.
            trimestre: Numéro du trimestre.
            **updates: Champs à mettre à jour.

        Returns:
            True si mis à jour.
        """
        if not updates:
            return False

        set_clauses = ["updated_at = CURRENT_TIMESTAMP"]
        params = []

        for key, value in updates.items():
            if key in (
                "genre",
                "absences_demi_journees",
                "absences_justifiees",
                "retards",
                "classe_id",
                "raw_text",
                "moyenne_generale",
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

        if len(set_clauses) == 1:  # Only updated_at
            return False

        params.extend([eleve_id, trimestre])
        self._execute_write(
            f"UPDATE eleves SET {', '.join(set_clauses)} WHERE eleve_id = ? AND trimestre = ?",
            params,
        )
        return True

    def delete(self, eleve_id: str, trimestre: int | None = None) -> bool:
        """Supprime un enregistrement élève.

        Args:
            eleve_id: Identifiant de l'élève.
            trimestre: Numéro du trimestre. Si None, supprime TOUS les trimestres.

        Returns:
            True si supprimé.
        """
        if trimestre is not None:
            self._execute_write(
                "DELETE FROM eleves WHERE eleve_id = ? AND trimestre = ?",
                [eleve_id, trimestre],
            )
        else:
            # Delete all trimesters for this student
            self._execute_write(
                "DELETE FROM eleves WHERE eleve_id = ?",
                [eleve_id],
            )
        return True
