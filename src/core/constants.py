from datetime import date
from pathlib import Path

# Chemins racine du projet
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Chemins des données
DATA_DIR = PROJECT_ROOT / "data"
DATA_RAW_DIR = DATA_DIR / "raw"
DATA_PROCESSED_DIR = DATA_DIR / "processed"
DATA_GROUND_TRUTH_DIR = DATA_DIR / "ground_truth"
DATA_EXPORTS_DIR = DATA_DIR / "exports"
DATA_MAPPING_DIR = DATA_DIR / "mapping"

# Chemins notebooks
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"

# Chemins des bases de données
DATA_DB_DIR = DATA_DIR / "db"
DB_CHIRON = DATA_DB_DIR / "chiron.duckdb"

# Chemins métriques LLM
DATA_LLM_METRICS_DIR = DATA_PROCESSED_DIR / "llm_metrics"
DB_LLM_METRICS = DATA_LLM_METRICS_DIR / "metrics.duckdb"

# Chemins logs
DATA_LOGS_DIR = DATA_PROCESSED_DIR / "logs"


def get_current_school_year() -> str:
    """Return current school year as 'YYYY-YYYY+1'.

    School year runs September to August:
    - Sept 2025 to Aug 2026 → '2025-2026'
    - Jan 2026 to Aug 2026 → '2025-2026'
    """
    today = date.today()
    if today.month >= 9:
        return f"{today.year}-{today.year + 1}"
    return f"{today.year - 1}-{today.year}"
