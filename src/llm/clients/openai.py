"""Client OpenAI avec gestion des métriques.

Supporte les modèles GPT (4.1, 4o, 5).
"""

import logging

from openai import AsyncOpenAI

from src.llm.base import LLMClient, LLMRawResponse
from src.llm.config import settings
from src.llm.pricing import PricingCalculator

logger = logging.getLogger(__name__)


class OpenAIClient(LLMClient):
    """Client pour les modèles OpenAI (GPT-4.1, GPT-4o, GPT-5)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        """Initialise le client OpenAI.

        Args:
            api_key: Clé API OpenAI. Si None, utilise settings.openai_api_key
            model: Nom du modèle. Si None, utilise settings.get_model("openai")
        """
        self._api_key = api_key or settings.openai_api_key
        self._model = model or settings.get_model("openai")
        self._client = AsyncOpenAI(api_key=self._api_key)
        self.pricing_calc = PricingCalculator("openai", settings.openai_pricing)
        logger.info(f"OpenAIClient initialisé avec modèle: {self._model}")

    @property
    def provider_name(self) -> str:
        """Retourne le nom du provider."""
        return "openai"

    @property
    def model_name(self) -> str:
        """Retourne le nom du modèle."""
        return self._model

    async def _do_call(
        self,
        messages: list[dict[str, str]],
        model: str,
        **kwargs,
    ) -> LLMRawResponse:
        """Effectue l'appel à l'API OpenAI.

        Gère les spécificités GPT-5 (temperature=1 only, max_completion_tokens).
        """
        # Vérifier si c'est un modèle GPT-5
        is_gpt5 = model.startswith("gpt-5")

        # GPT-5 ne supporte que temperature=1 (défaut), donc on le retire si présent
        if is_gpt5:
            kwargs.pop("temperature", None)
        elif "temperature" not in kwargs:
            kwargs["temperature"] = settings.default_temperature

        # GPT-5 utilise max_completion_tokens au lieu de max_tokens
        if is_gpt5 and "max_tokens" in kwargs:
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")

        max_tokens_key = "max_completion_tokens" if is_gpt5 else "max_tokens"

        if max_tokens_key not in kwargs:
            kwargs[max_tokens_key] = settings.default_max_tokens

        # GPT-5 utilise des tokens pour le raisonnement interne
        if is_gpt5 and kwargs.get(max_tokens_key, 0) < 16000:
            kwargs[max_tokens_key] = 16000

        # Appel API
        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs,
        )

        # Extraire les données
        message = response.choices[0].message
        content = message.content

        # Debug: vérifier si content est None ou vide
        if content is None or content.strip() == "":
            logger.warning(
                f"[WARNING] OpenAI retourné content vide/None pour {model}\n"
                f"   Message object: {message}\n"
                f"   Refusal: {getattr(message, 'refusal', None)}\n"
                f"   Finish reason: {response.choices[0].finish_reason}"
            )
            content = content or ""

        return LLMRawResponse(
            content=content,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            model=model,
        )
