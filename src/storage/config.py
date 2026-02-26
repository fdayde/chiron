"""Configuration du module de stockage."""

from pathlib import Path

from pydantic_settings import BaseSettings

from src.core.constants import DATA_DIR


class StorageSettings(BaseSettings):
    """Paramètres de stockage/base de données."""

    db_path: Path = DATA_DIR / "db" / "chiron.duckdb"
    data_retention_days: int = 30

    model_config = {"env_prefix": "CHIRON_STORAGE_"}


storage_settings = StorageSettings()
