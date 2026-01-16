"""UI configuration."""

from pydantic_settings import BaseSettings


class UISettings(BaseSettings):
    """Settings for the Streamlit UI."""

    api_base_url: str = "http://localhost:8000"
    page_title: str = "Chiron - Conseil de Classe"
    page_icon: str = "📚"

    model_config = {"env_prefix": "CHIRON_UI_"}


ui_settings = UISettings()
