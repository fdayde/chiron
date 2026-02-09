"""Module de génération de synthèses LLM."""

from src.generation.generator import GenerationResult, SyntheseGenerator
from src.generation.prompt_builder import PromptBuilder
from src.generation.prompts import (
    CURRENT_PROMPT,
    get_prompt,
    get_prompt_hash,
    list_prompts,
)

__all__ = [
    # Generator
    "SyntheseGenerator",
    "GenerationResult",
    # Prompt builder
    "PromptBuilder",
    # Versioned prompts
    "CURRENT_PROMPT",
    "get_prompt",
    "get_prompt_hash",
    "list_prompts",
]
