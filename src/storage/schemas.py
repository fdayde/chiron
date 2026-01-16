"""Database schema definitions for DuckDB."""

TABLES = {
    "classes": """
        CREATE TABLE IF NOT EXISTS classes (
            classe_id VARCHAR PRIMARY KEY,
            nom VARCHAR NOT NULL,
            niveau VARCHAR,
            annee_scolaire VARCHAR DEFAULT '2024-2025',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "eleves": """
        CREATE TABLE IF NOT EXISTS eleves (
            eleve_id VARCHAR PRIMARY KEY,
            classe_id VARCHAR REFERENCES classes(classe_id),
            genre VARCHAR(1),
            trimestre INTEGER,
            absences_demi_journees INTEGER,
            absences_justifiees BOOLEAN,
            retards INTEGER,
            engagements JSON,
            parcours JSON,
            evenements JSON,
            matieres JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "syntheses": """
        CREATE TABLE IF NOT EXISTS syntheses (
            synthese_id VARCHAR PRIMARY KEY,
            eleve_id VARCHAR REFERENCES eleves(eleve_id),
            trimestre INTEGER,
            synthese_texte TEXT,
            alertes JSON,
            reussites JSON,
            posture_generale VARCHAR,
            axes_travail JSON,
            status VARCHAR DEFAULT 'generated',
            provider VARCHAR,
            model VARCHAR,
            tokens_used INTEGER,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            validated_at TIMESTAMP,
            validated_by VARCHAR
        )
    """,
    "exemples_fewshot": """
        CREATE TABLE IF NOT EXISTS exemples_fewshot (
            exemple_id VARCHAR PRIMARY KEY,
            classe_id VARCHAR REFERENCES classes(classe_id),
            eleve_data JSON,
            synthese_prof TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
}

# Order matters for foreign key constraints
TABLE_ORDER = ["classes", "eleves", "syntheses", "exemples_fewshot"]
