"""Configuration centralisée du logging pour le projet.

Ce module permet de configurer facilement le logging avec :
- Logs console (niveau INFO)
- Logs fichier (niveau DEBUG)
- Nom du log identique au batch JSON
"""

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.core.constants import DATA_PROCESSED_DIR

# Répertoire des logs
LOGS_DIR = DATA_PROCESSED_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)


def setup_batch_logging(
    batch_id: str | None = None,
    console_level: int = logging.INFO,
) -> tuple[logging.Logger, str, str]:
    """Configure le logging pour un batch d'extraction.

    Crée un fichier de log nommé batch_{batch_id}.log pour correspondre
    au fichier JSON batch_{batch_id}.json.

    Args:
        batch_id: ID du batch (timestamp). Si None, généré automatiquement
        console_level: Niveau de log pour la console (INFO par défaut)

    Returns:
        Tuple (logger, batch_id, log_file_path)

    Usage dans notebook:
        >>> from src.core.logging_config import setup_batch_logging
        >>> logger, batch_id, log_file = setup_batch_logging()
        >>> logger.info("Démarrage extraction")
        >>> # Utiliser batch_id pour save_batch_results()
    """
    # Générer batch_id si non fourni (même format que storage.py)
    if batch_id is None:
        batch_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Nom du fichier de log (même nom que le JSON)
    log_file_name = f"batch_{batch_id}.log"
    log_file_path = LOGS_DIR / log_file_name

    # Récupérer le logger racine
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Nettoyer les handlers existants pour éviter les doublons
    logger.handlers.clear()

    # Format détaillé avec timestamp pour fichier
    detailed_format = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Format simplifié pour console
    simple_format = logging.Formatter(
        fmt="%(levelname)-8s | %(message)s",
    )

    # Handler fichier avec rotation
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_format)
    logger.addHandler(file_handler)

    # Handler console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(simple_format)
    logger.addHandler(console_handler)

    logger.info(f"Logs sauvegardés dans : {log_file_path}")
    logger.info(f"🆔 Batch ID : {batch_id}")

    return logger, batch_id, str(log_file_path)


def get_log_file_for_batch(batch_id: str) -> Path:
    """Retourne le chemin du fichier de log pour un batch_id donné.

    Args:
        batch_id: ID du batch

    Returns:
        Path vers le fichier de log
    """
    return LOGS_DIR / f"batch_{batch_id}.log"
