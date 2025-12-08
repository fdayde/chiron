"""Client Mistral avec gestion des métriques.

Supporte les modèles Mistral (Large, Small).
"""

import asyncio
import logging
import time

from mistralai import Mistral

from src.llm.base import LLMClient
from src.llm.config import settings
from src.llm.metrics import LLMCallMetrics, metrics_collector
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

    async def call(
        self,
        messages: list[dict[str, str]],
        **kwargs,
    ) -> dict:
        """Effectue un appel à l'API Mistral.

        Args:
            messages: Liste de messages au format
                [{"role": "user/assistant/system", "content": "..."}]
            **kwargs: Paramètres additionnels (temperature, max_tokens, model, etc.)

        Returns:
            dict avec content, prompt_tokens, completion_tokens, total_tokens, model

        Raises:
            Exception: En cas d'erreur API
        """
        # Extraire le modèle (override possible via kwargs)
        model = kwargs.pop("model", self._model)

        # Paramètres par défaut
        if "temperature" not in kwargs:
            kwargs["temperature"] = settings.default_temperature

        if "max_tokens" not in kwargs:
            kwargs["max_tokens"] = settings.default_max_tokens

        start_time = time.time()
        success = False
        error_type = None

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
            # Pas d'event loop en cours (peut arriver), on continue
            pass

        try:
            # Appel API
            try:
                response = await self._client.chat.complete_async(
                    model=model,
                    messages=messages,
                    **kwargs,
                )
            except RuntimeError as e:
                # Capturer TOUS les problèmes d'event loop
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
                    # Event loop problématique → recréer le client
                    logger.warning(
                        f"Problème d'event loop détecté, recréation du client Mistral... (erreur: {str(e)[:100]})"
                    )
                    self._client = Mistral(api_key=self._api_key)
                    # Retry
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
                # Forcer content à chaîne vide si None
                content = content or ""

            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens

            success = True
            latency_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Mistral call réussi: {model} - {total_tokens} tokens - "
                f"{latency_ms:.0f}ms - Content length: {len(content)} chars"
            )

            # Collecter métriques
            metric = LLMCallMetrics(
                provider=self.provider_name,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                success=success,
                error_type=None,
                cost_usd=self.pricing_calc.calculate(
                    model, prompt_tokens, completion_tokens
                ),
            )
            metrics_collector.collect(metric)

            return {
                "content": content,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "model": model,
            }

        except Exception as e:
            error_type = type(e).__name__
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"Erreur Mistral call: {error_type} - {str(e)}")

            # Collecter métriques d'erreur
            metric = LLMCallMetrics(
                provider=self.provider_name,
                model=model,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=latency_ms,
                success=False,
                error_type=error_type,
                cost_usd=0.0,
            )
            metrics_collector.collect(metric)

            raise
