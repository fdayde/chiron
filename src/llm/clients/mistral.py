"""Client Mistral avec gestion des métriques.

Supporte les modèles Mistral (Large, Small).
"""

import asyncio
import logging

from mistralai import Mistral

from src.llm.base import LLMClient, LLMRawResponse
from src.llm.config import settings
from src.llm.pricing import PricingCalculator

logger = logging.getLogger(__name__)


class MistralClient(LLMClient):
    """Client pour les modèles Mistral (Large, Small)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        """Initialise le client Mistral.

        Args:
            api_key: Clé API Mistral. Si None, utilise settings.mistral_api_key
            model: Nom du modèle. Si None, utilise settings.get_model("mistral")
        """
        self._api_key = api_key or settings.mistral_api_key
        self._model = model or settings.get_model("mistral")
        self._client = Mistral(api_key=self._api_key)
        self._last_loop = None  # Pour détecter les changements d'event loop
        self.pricing_calc = PricingCalculator("mistral", settings.mistral_pricing)
        logger.info(f"MistralClient initialisé avec modèle: {self._model}")

    @property
    def provider_name(self) -> str:
        """Retourne le nom du provider."""
        return "mistral"

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
        """Effectue l'appel à l'API Mistral.

        Gère la détection/recréation d'event loop (problème connu du SDK Mistral).
        """
        # Paramètres par défaut
        if "temperature" not in kwargs:
            kwargs["temperature"] = settings.default_temperature

        if "max_tokens" not in kwargs:
            kwargs["max_tokens"] = settings.default_max_tokens

        # Protection proactive : vérifier si l'event loop a changé
        try:
            current_loop = asyncio.get_running_loop()
            if self._last_loop is not None and self._last_loop != current_loop:
                logger.warning(
                    "Event loop changé détecté, recréation préventive du client Mistral..."
                )
                self._client = Mistral(api_key=self._api_key)
            self._last_loop = current_loop
        except RuntimeError:
            pass

        # Appel API avec retry sur erreur d'event loop
        try:
            response = await self._client.chat.complete_async(
                model=model,
                messages=messages,
                **kwargs,
            )
        except RuntimeError as e:
            error_msg = str(e).lower()
            if any(
                keyword in error_msg
                for keyword in [
                    "event loop",
                    "asyncio",
                    "different event loop",
                    "loop is closed",
                ]
            ):
                logger.warning(
                    f"Problème d'event loop détecté, recréation du client Mistral... "
                    f"(erreur: {str(e)[:100]})"
                )
                self._client = Mistral(api_key=self._api_key)
                response = await self._client.chat.complete_async(
                    model=model,
                    messages=messages,
                    **kwargs,
                )
            else:
                raise

        # Extraire les données
        message = response.choices[0].message
        content = message.content

        # Debug: vérifier si content est None ou vide
        if content is None or content.strip() == "":
            logger.warning(
                f"[WARNING] Mistral retourné content vide/None pour {model}\n"
                f"   Message object: {message}\n"
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
