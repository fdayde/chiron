"""UI configuration for NiceGUI."""

from __future__ import annotations

from pydantic_settings import BaseSettings

from src.llm.config import settings as llm_settings
from src.llm.pricing import PricingCalculator

# Estimation tokens par bulletin (basé sur ground truth)
TOKENS_INPUT_PER_BULLETIN = 2000
TOKENS_OUTPUT_PER_BULLETIN = 500


class UISettings(BaseSettings):
    """Settings for the NiceGUI UI."""

    api_base_url: str = "http://localhost:8080"
    default_provider: str = "mistral"
    default_model: str = ""  # Empty = use provider default from llm_settings
    default_temperature: float = llm_settings.default_temperature

    model_config = {"env_prefix": "CHIRON_UI_"}


ui_settings = UISettings()


def get_llm_providers() -> dict:
    """Retourne les providers LLM disponibles avec leurs modèles."""
    return {
        "openai": {
            "name": "OpenAI",
            "models": list(llm_settings.openai_pricing.keys()),
            "default": llm_settings.default_openai_model,
        },
        "anthropic": {
            "name": "Anthropic",
            "models": list(llm_settings.anthropic_pricing.keys()),
            "default": llm_settings.default_anthropic_model,
        },
        "mistral": {
            "name": "Mistral",
            "models": list(llm_settings.mistral_pricing.keys()),
            "default": llm_settings.default_mistral_model,
        },
    }


LLM_PROVIDERS = get_llm_providers()


def estimate_cost_per_bulletin(provider: str, model: str) -> float:
    """Estime le coût par bulletin pour un modèle donné."""
    calc = PricingCalculator(provider, llm_settings.get_pricing(provider))
    return calc.calculate(model, TOKENS_INPUT_PER_BULLETIN, TOKENS_OUTPUT_PER_BULLETIN)


def format_model_label(provider: str, model: str) -> str:
    """Formate le label du modèle avec le coût estimé."""
    cost = estimate_cost_per_bulletin(provider, model)
    if cost >= 0.01:
        return f"{model} (~${cost:.3f}/eleve)"
    elif cost >= 0.001:
        return f"{model} (~${cost:.4f}/eleve)"
    else:
        return f"{model} (~${cost:.5f}/eleve)"


def estimate_total_cost(provider: str, model: str, nb_eleves: int) -> float:
    """Estime le coût total pour N élèves."""
    return estimate_cost_per_bulletin(provider, model) * nb_eleves
