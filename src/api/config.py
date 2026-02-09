"""API configuration."""

from pydantic_settings import BaseSettings


class APISettings(BaseSettings):
    """Settings for the API server."""

    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:8501"]  # Streamlit default

    model_config = {"env_prefix": "CHIRON_API_"}


api_settings = APISettings()
