"""Database schema definitions for DuckDB.

Architecture à deux bases de données (séparation RGPD) :

┌─────────────────────────────────────────────────────────────────┐
│  data/db/chiron.duckdb - Données pseudonymisées                 │
│  ✓ Peut être synchronisé, backupé, partagé                      │
│  Tables: classes, eleves, syntheses, exemples_fewshot           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  data/db/privacy.duckdb - Mapping identités (CONFIDENTIEL)      │
│  ✗ NE JAMAIS partager, synchroniser ou backuper sur le cloud    │
│  Table: mapping_identites (eleve_id ↔ nom/prénom réels)         │
│  Géré par: src/privacy/pseudonymizer.py                         │
└─────────────────────────────────────────────────────────────────┘
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
            annee_scolaire VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "eleves": """
        CREATE TABLE IF NOT EXISTS eleves (
            eleve_id VARCHAR NOT NULL,
            classe_id VARCHAR REFERENCES classes(classe_id),
            trimestre INTEGER NOT NULL,

            -- Données extraites (ANONYMISÉES)
            raw_text TEXT,
            moyenne_generale FLOAT,

            -- Champs structurés
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
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- Clé primaire composite : un élève peut avoir plusieurs trimestres
            PRIMARY KEY (eleve_id, trimestre)
        )
    """,
    "syntheses": """
        CREATE TABLE IF NOT EXISTS syntheses (
            id VARCHAR PRIMARY KEY,
            eleve_id VARCHAR NOT NULL,
            trimestre INTEGER NOT NULL,
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
