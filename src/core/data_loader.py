"""Chargement de données (ground truth, exemples, etc.)."""

import json
from pathlib import Path

from src.core.models import EleveGroundTruth, GroundTruthDataset


def load_ground_truth(json_path: str | Path) -> GroundTruthDataset:
    """Charge un dataset ground truth depuis un fichier JSON.

    Args:
        json_path: Chemin vers le fichier JSON.

    Returns:
        GroundTruthDataset validé par Pydantic.
    """
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    return GroundTruthDataset(**data)


def load_ground_truth_eleves(json_path: str | Path) -> list[EleveGroundTruth]:
    """Charge uniquement les élèves depuis un fichier ground truth.

    Args:
        json_path: Chemin vers le fichier JSON.

    Returns:
        Liste d'EleveGroundTruth (avec synthese_ground_truth).
    """
    return load_ground_truth(json_path).eleves
