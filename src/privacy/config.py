"""Privacy module configuration."""

from pydantic_settings import BaseSettings

from src.core.constants import DATA_DIR


class PrivacySettings(BaseSettings):
    """Settings for privacy/pseudonymization."""

    pseudonym_prefix: str = "ELEVE_"
    mapping_table: str = "mapping_identites"
    db_path: str = str(DATA_DIR / "db" / "chiron.duckdb")

    model_config = {"env_prefix": "CHIRON_PRIVACY_"}


privacy_settings = PrivacySettings()
