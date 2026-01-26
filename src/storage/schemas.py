"""Database schema definitions for DuckDB.

Deux bases de données :
- chiron.duckdb : données pseudonymisées (peut être synchronisé/backupé)
- privacy.duckdb : mapping nom ↔ eleve_id (reste en local uniquement)
"""

# ============================================================================
# CHIRON.DUCKDB - Données pseudonymisées
# ============================================================================

TABLES = {
    "classes": """
        CREATE TABLE IF NOT EXISTS classes (
            classe_id VARCHAR PRIMARY KEY,
            nom VARCHAR NOT NULL,
            niveau VARCHAR,
            etablissement VARCHAR,
            annee_scolaire VARCHAR DEFAULT '2024-2025',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "eleves": """
        CREATE TABLE IF NOT EXISTS eleves (
            eleve_id VARCHAR PRIMARY KEY,
            classe_id VARCHAR REFERENCES classes(classe_id),
            trimestre INTEGER,

            -- Données extraites (ANONYMISÉES)
            raw_text_ocr TEXT,
            raw_text_anonymise TEXT,
            donnees_json JSON,

            -- Champs structurés (extraits de donnees_json)
            genre VARCHAR,
            absences_demi_journees INTEGER,
            absences_justifiees BOOLEAN,
            retards INTEGER,
            engagements JSON,
            parcours JSON,
            evenements JSON,
            matieres JSON,

            -- Métadonnées OCR
            ocr_provider VARCHAR,
            ocr_model VARCHAR,
            ocr_cost FLOAT,
            ocr_duration_ms INTEGER,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "syntheses": """
        CREATE TABLE IF NOT EXISTS syntheses (
            id VARCHAR PRIMARY KEY,
            eleve_id VARCHAR REFERENCES eleves(eleve_id),
            trimestre INTEGER,
            status VARCHAR DEFAULT 'draft',

            -- Contenu généré
            synthese_texte TEXT,
            llm_response_raw TEXT,
            alertes_json JSON,
            reussites_json JSON,
            posture_generale VARCHAR,
            axes_travail_json JSON,

            -- Métadonnées LLM
            llm_provider VARCHAR,
            llm_model VARCHAR,
            prompt_template VARCHAR,
            prompt_hash VARCHAR,
            tokens_input INTEGER,
            tokens_output INTEGER,
            tokens_total INTEGER,
            llm_cost FLOAT,
            llm_duration_ms INTEGER,
            llm_temperature FLOAT,

            -- Erreurs/retry
            retry_count INTEGER DEFAULT 0,
            error_message TEXT,

            -- Validation
            validated_by VARCHAR,
            validated_at TIMESTAMP,
            edited_at TIMESTAMP,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(eleve_id, trimestre)
        )
    """,
    "exemples_fewshot": """
        CREATE TABLE IF NOT EXISTS exemples_fewshot (
            id VARCHAR PRIMARY KEY,
            classe_id VARCHAR REFERENCES classes(classe_id),
            eleve_data JSON,
            synthese_prof TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
}

# Order matters for foreign key constraints
TABLE_ORDER = ["classes", "eleves", "syntheses", "exemples_fewshot"]


# ============================================================================
# PRIVACY.DUCKDB - Mapping nom ↔ eleve_id (SÉPARÉ, local uniquement)
# ============================================================================

PRIVACY_TABLES = {
    "eleve_mapping": """
        CREATE TABLE IF NOT EXISTS eleve_mapping (
            eleve_id VARCHAR PRIMARY KEY,
            nom_original VARCHAR NOT NULL,
            prenom_original VARCHAR,
            nom_complet VARCHAR,
            classe_id VARCHAR NOT NULL,
            etablissement VARCHAR,
            genre VARCHAR(1),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
}

PRIVACY_TABLE_ORDER = ["eleve_mapping"]


# ============================================================================
# Migration helpers
# ============================================================================


def get_migration_sql(from_version: str, to_version: str) -> list[str]:
    """Retourne les requêtes SQL pour migrer entre versions.

    Args:
        from_version: Version actuelle (ex: "1.0.0")
        to_version: Version cible (ex: "1.1.0")

    Returns:
        Liste de requêtes SQL à exécuter.
    """
    migrations = {
        ("1.0.0", "1.1.0"): [
            # Ajouter les nouveaux champs à eleves
            "ALTER TABLE eleves ADD COLUMN IF NOT EXISTS raw_text_ocr TEXT",
            "ALTER TABLE eleves ADD COLUMN IF NOT EXISTS raw_text_anonymise TEXT",
            "ALTER TABLE eleves ADD COLUMN IF NOT EXISTS donnees_json JSON",
            "ALTER TABLE eleves ADD COLUMN IF NOT EXISTS parcours JSON",
            "ALTER TABLE eleves ADD COLUMN IF NOT EXISTS evenements JSON",
            "ALTER TABLE eleves ADD COLUMN IF NOT EXISTS ocr_provider VARCHAR",
            "ALTER TABLE eleves ADD COLUMN IF NOT EXISTS ocr_model VARCHAR",
            "ALTER TABLE eleves ADD COLUMN IF NOT EXISTS ocr_cost FLOAT",
            "ALTER TABLE eleves ADD COLUMN IF NOT EXISTS ocr_duration_ms INTEGER",
            "ALTER TABLE eleves ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",
            # Ajouter les nouveaux champs à syntheses
            "ALTER TABLE syntheses ADD COLUMN IF NOT EXISTS llm_response_raw TEXT",
            "ALTER TABLE syntheses ADD COLUMN IF NOT EXISTS alertes_json JSON",
            "ALTER TABLE syntheses ADD COLUMN IF NOT EXISTS reussites_json JSON",
            "ALTER TABLE syntheses ADD COLUMN IF NOT EXISTS axes_travail_json JSON",
            "ALTER TABLE syntheses ADD COLUMN IF NOT EXISTS prompt_template VARCHAR",
            "ALTER TABLE syntheses ADD COLUMN IF NOT EXISTS prompt_hash VARCHAR",
            "ALTER TABLE syntheses ADD COLUMN IF NOT EXISTS tokens_input INTEGER",
            "ALTER TABLE syntheses ADD COLUMN IF NOT EXISTS tokens_output INTEGER",
            "ALTER TABLE syntheses ADD COLUMN IF NOT EXISTS tokens_total INTEGER",
            "ALTER TABLE syntheses ADD COLUMN IF NOT EXISTS llm_cost FLOAT",
            "ALTER TABLE syntheses ADD COLUMN IF NOT EXISTS llm_duration_ms INTEGER",
            "ALTER TABLE syntheses ADD COLUMN IF NOT EXISTS llm_temperature FLOAT",
            "ALTER TABLE syntheses ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0",
            "ALTER TABLE syntheses ADD COLUMN IF NOT EXISTS error_message TEXT",
            "ALTER TABLE syntheses ADD COLUMN IF NOT EXISTS edited_at TIMESTAMP",
            "ALTER TABLE syntheses ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",
            # Ajouter etablissement à classes
            "ALTER TABLE classes ADD COLUMN IF NOT EXISTS etablissement VARCHAR",
            "ALTER TABLE classes ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",
        ],
    }

    return migrations.get((from_version, to_version), [])
