"""Privacy module configuration.

IMPORTANT: La base privacy.duckdb contient les vrais noms des élèves.
Elle ne doit JAMAIS être partagée, synchronisée ou backupée sur le cloud.
Seule chiron.duckdb (données pseudonymisées) peut être partagée.
"""

from pydantic_settings import BaseSettings

from src.core.constants import DATA_DIR


class PrivacySettings(BaseSettings):
    """Settings for privacy/pseudonymization.

    La table mapping_identites est stockée dans une base SÉPARÉE (privacy.duckdb)
    pour garantir que les vrais noms ne soient jamais mélangés avec les données
    pseudonymisées qui peuvent être partagées.
    """

    pseudonym_prefix: str = "ELEVE_"
    mapping_table: str = "mapping_identites"
    # Base séparée pour les données sensibles (vrais noms)
    db_path: str = str(DATA_DIR / "db" / "privacy.duckdb")

    model_config = {"env_prefix": "CHIRON_PRIVACY_"}


privacy_settings = PrivacySettings()
