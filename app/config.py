"""UI configuration."""

import streamlit as st
from api_client import ChironAPIClient
from pydantic_settings import BaseSettings

from src.llm.config import settings as llm_settings

# Estimation tokens par bulletin (basé sur ground truth)
TOKENS_INPUT_PER_BULLETIN = 2000
TOKENS_OUTPUT_PER_BULLETIN = 500


class UISettings(BaseSettings):
    """Settings for the Streamlit UI."""

    api_base_url: str = "http://localhost:8000"
    page_title: str = "Chiron - Conseil de Classe"
    page_icon: str = "📚"

    # LLM generation defaults - référence la config centrale
    default_provider: str = "openai"
    default_model: str = ""  # Empty = use provider default from llm_settings
    default_temperature: float = llm_settings.default_temperature

    model_config = {"env_prefix": "CHIRON_UI_"}


ui_settings = UISettings()


def get_llm_providers() -> dict:
    """Retourne les providers LLM disponibles avec leurs modèles.

    Les modèles sont extraits de src/llm/config.py pour éviter la duplication.
    """
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


# Pour compatibilité avec le code existant
LLM_PROVIDERS = get_llm_providers()


def estimate_cost_per_bulletin(provider: str, model: str) -> float:
    """Estime le coût par bulletin pour un modèle donné.

    Args:
        provider: Provider LLM (openai, anthropic, mistral).
        model: Nom du modèle.

    Returns:
        Coût estimé en USD par bulletin.
    """
    pricing = llm_settings.get_pricing(provider)
    if model not in pricing:
        return 0.0

    input_price, output_price = pricing[model]
    # Prix par million de tokens -> prix par token -> prix par bulletin
    cost = (TOKENS_INPUT_PER_BULLETIN * input_price / 1_000_000) + (
        TOKENS_OUTPUT_PER_BULLETIN * output_price / 1_000_000
    )
    return cost


def format_model_label(provider: str, model: str) -> str:
    """Formate le label du modèle avec le coût estimé.

    Args:
        provider: Provider LLM.
        model: Nom du modèle.

    Returns:
        Label formaté, ex: "gpt-5-mini (~$0.002/élève)"
    """
    cost = estimate_cost_per_bulletin(provider, model)
    if cost >= 0.01:
        return f"{model} (~${cost:.3f}/élève)"
    elif cost >= 0.001:
        return f"{model} (~${cost:.4f}/élève)"
    else:
        return f"{model} (~${cost:.5f}/élève)"


def estimate_total_cost(provider: str, model: str, nb_eleves: int) -> float:
    """Estime le coût total pour N élèves.

    Args:
        provider: Provider LLM.
        model: Nom du modèle.
        nb_eleves: Nombre d'élèves.

    Returns:
        Coût total estimé en USD.
    """
    return estimate_cost_per_bulletin(provider, model) * nb_eleves


def calculate_actual_cost(
    provider: str, model: str, tokens_input: int, tokens_output: int
) -> float:
    """Calcule le coût réel basé sur les tokens utilisés.

    Args:
        provider: Provider LLM.
        model: Nom du modèle.
        tokens_input: Nombre de tokens en entrée.
        tokens_output: Nombre de tokens en sortie.

    Returns:
        Coût réel en USD.
    """
    pricing = llm_settings.get_pricing(provider)
    if model not in pricing:
        return 0.0

    input_price, output_price = pricing[model]
    cost = (tokens_input * input_price / 1_000_000) + (
        tokens_output * output_price / 1_000_000
    )
    return cost


@st.cache_resource
def get_api_client() -> ChironAPIClient:
    """Get cached API client.

    Centralized factory for the Chiron API client.
    Uses Streamlit's cache_resource to maintain a single instance.
    """
    return ChironAPIClient()
