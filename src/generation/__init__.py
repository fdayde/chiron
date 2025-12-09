"""Module de génération de synthèses LLM."""

from src.generation.generator import SyntheseGenerator
from src.generation.prompt_builder import PromptBuilder

__all__ = ["PromptBuilder", "SyntheseGenerator"]
