"""Storage module configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings

from src.core.constants import DATA_DIR


class StorageSettings(BaseSettings):
    """Settings for storage/database."""

    db_path: Path = DATA_DIR / "db" / "chiron.duckdb"

    model_config = {"env_prefix": "CHIRON_STORAGE_"}


storage_settings = StorageSettings()
