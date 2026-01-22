"""Configuration du module LLM.

Ce module centralise tous les paramètres de configuration pour les appels LLM,
incluant les API keys, modèles, retry, rate limits et timeouts.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """Configuration des clients LLM.

    Charge automatiquement les variables depuis .env.
    Tous les paramètres peuvent être overridés programmatiquement.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Keys (optionnelles pour permettre le dev sans toutes les clés)
    openai_api_key: str = Field(default="", description="Clé API OpenAI")
    anthropic_api_key: str = Field(default="", description="Clé API Anthropic")
    mistral_api_key: str = Field(default="", description="Clé API Mistral LLM")
    mistral_ocr_api_key: str = Field(default="", description="Clé API Mistral OCR")

    # PDF Parser configuration
    pdf_parser_type: str = Field(
        default="pdfplumber",
        description="Type de parser PDF (pdfplumber ou mistral_ocr)",
    )
    mistral_ocr_model: str = Field(
        default="mistral-ocr-latest",
        description="Modèle Mistral OCR à utiliser",
    )
    mistral_ocr_cost_per_1000_pages: float = Field(
        default=2.0,
        description="Coût Mistral OCR en USD pour 1000 pages",
    )

    # Modèles par défaut (production)
    default_openai_model: str = Field(
        default="gpt-5-mini", description="Modèle OpenAI par défaut"
    )
    default_anthropic_model: str = Field(
        default="claude-sonnet-4-5", description="Modèle Anthropic par défaut"
    )
    default_mistral_model: str = Field(
        default="mistral-large-latest", description="Modèle Mistral par défaut"
    )

    # Modèles de test (moins chers)
    test_openai_model: str = Field(
        default="gpt-5-nano", description="Modèle OpenAI pour tests"
    )
    test_anthropic_model: str = Field(
        default="claude-haiku-4-5", description="Modèle Anthropic pour tests"
    )
    test_mistral_model: str = Field(
        default="mistral-small-latest", description="Modèle Mistral pour tests"
    )

    # Flag pour basculer entre modèles de prod et test
    use_test_models: bool = Field(
        default=False, description="Utiliser les modèles de test"
    )

    # Retry configuration
    max_retries: int = Field(default=3, ge=0, description="Nombre max de tentatives")
    backoff_factor: float = Field(
        default=2.0, gt=0, description="Facteur multiplicateur backoff"
    )

    # Rate limits (requêtes par minute)
    openai_rpm: int = Field(default=500, gt=0, description="Rate limit OpenAI (RPM)")
    anthropic_rpm: int = Field(
        default=50, gt=0, description="Rate limit Anthropic (RPM)"
    )
    mistral_rpm: int = Field(default=100, gt=0, description="Rate limit Mistral (RPM)")

    # Timeouts
    default_timeout: int = Field(
        default=30, gt=0, description="Timeout par défaut en secondes"
    )

    # Paramètres LLM par défaut
    default_temperature: float = Field(
        default=0.0, ge=0, le=2, description="Température par défaut"
    )
    default_max_tokens: int = Field(
        default=16384,
        gt=0,
        description="Max tokens de sortie par défaut (tous modèles)",
    )

    # Pricing OpenAI (USD par million de tokens) - Input / Output
    # Source: https://openai.com/api/pricing/
    openai_pricing: dict[str, tuple[float, float]] = {
        "gpt-5": (1.25, 10.00),
        "gpt-5-mini": (0.25, 2.00),
        "gpt-5-nano": (0.05, 0.40),
        "gpt-5-chat-latest": (1.25, 10.00),
        "gpt-5-codex": (1.25, 10.00),
        "gpt-5-pro": (15.00, 120.00),
        "gpt-4.1": (2.00, 8.00),
        "gpt-4.1-mini": (0.40, 1.60),
        "gpt-4.1-nano": (0.10, 0.40),
        "gpt-4o": (2.50, 10.00),
        "gpt-4o-mini": (0.15, 0.60),
    }

    # Pricing Anthropic (USD par million de tokens) - Input / Output
    # Source: https://www.anthropic.com/pricing
    anthropic_pricing: dict[str, tuple[float, float]] = {
        "claude-sonnet-4-5": (3.00, 15.00),
        "claude-haiku-4-5": (1.00, 5.00),
    }

    # Pricing Mistral (USD par million de tokens) - Input / Output
    # Source: https://mistral.ai/technology/#pricing
    mistral_pricing: dict[str, tuple[float, float]] = {
        "mistral-large-latest": (2.00, 6.00),
        "mistral-medium-latest": (2.00, 5.00),
        "mistral-small-latest": (0.50, 1.50),
    }

    def get_model(self, provider: str) -> str:
        """Retourne le modèle approprié selon le provider et le flag use_test_models.

        Args:
            provider: Nom du provider (openai/anthropic/mistral)

        Returns:
            Nom du modèle à utiliser

        Raises:
            ValueError: Si le provider est inconnu
        """
        provider_lower = provider.lower()
        if self.use_test_models:
            if provider_lower == "openai":
                return self.test_openai_model
            elif provider_lower == "anthropic":
                return self.test_anthropic_model
            elif provider_lower == "mistral":
                return self.test_mistral_model
        else:
            if provider_lower == "openai":
                return self.default_openai_model
            elif provider_lower == "anthropic":
                return self.default_anthropic_model
            elif provider_lower == "mistral":
                return self.default_mistral_model

        raise ValueError(f"Provider inconnu: {provider}")

    def get_rpm(self, provider: str) -> int:
        """Retourne le rate limit (RPM) pour un provider.

        Args:
            provider: Nom du provider (openai/anthropic/mistral)

        Returns:
            Rate limit en requêtes par minute

        Raises:
            ValueError: Si le provider est inconnu
        """
        provider_lower = provider.lower()
        if provider_lower == "openai":
            return self.openai_rpm
        elif provider_lower == "anthropic":
            return self.anthropic_rpm
        elif provider_lower == "mistral":
            return self.mistral_rpm
        raise ValueError(f"Provider inconnu: {provider}")


# Instance globale des settings
settings = LLMSettings()
