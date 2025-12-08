from pathlib import Path

# Chemins racine du projet
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Chemins des donnees
DATA_DIR = PROJECT_ROOT / "data"
DATA_RAW_DIR = DATA_DIR / "raw"
DATA_PROCESSED_DIR = DATA_DIR / "processed"

# Chemins des donnees sources V1
DATA_RAW_PACTONCO_V1_DIR = DATA_RAW_DIR / "Donnees sources pactOnco V1"
DATA_RAW_AVIS_CT_DIR = DATA_RAW_PACTONCO_V1_DIR / "Avis CT"

# Chemins notebooks
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"

# Chemins des bases de données
DATA_DB_DIR = DATA_PROCESSED_DIR / "extractions"
DB_PDF_EXTRACTIONS = DATA_DB_DIR / "pdf_extractions.duckdb"

# Chemins métriques LLM
DATA_LLM_METRICS_DIR = DATA_PROCESSED_DIR / "llm_metrics"
DB_LLM_METRICS = DATA_LLM_METRICS_DIR / "metrics.duckdb"

# Chemins logs
DATA_LOGS_DIR = DATA_PROCESSED_DIR / "logs"
