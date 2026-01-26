"""UI configuration."""

from pydantic_settings import BaseSettings

from src.llm.config import settings as llm_settings


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
