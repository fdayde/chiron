"""Client OpenAI avec gestion des métriques.

Supporte les modèles GPT (4.1, 4o, 5).
"""

import logging
import time

from openai import AsyncOpenAI

from src.llm.base import LLMClient
from src.llm.config import settings
from src.llm.metrics import LLMCallMetrics, metrics_collector
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

    async def call(
        self,
        messages: list[dict[str, str]],
        **kwargs,
    ) -> dict:
        """Effectue un appel à l'API OpenAI.

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

        # Vérifier si c'est un modèle GPT-5
        is_gpt5 = model.startswith("gpt-5")

        # Paramètres par défaut
        # GPT-5 ne supporte que temperature=1 (défaut), donc on le retire si présent
        if is_gpt5:
            kwargs.pop("temperature", None)
        elif "temperature" not in kwargs:
            kwargs["temperature"] = settings.default_temperature

        # GPT-5 utilise max_completion_tokens au lieu de max_tokens
        # Convertir max_tokens en max_completion_tokens si présent
        if is_gpt5 and "max_tokens" in kwargs:
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")

        max_tokens_key = "max_completion_tokens" if is_gpt5 else "max_tokens"

        if max_tokens_key not in kwargs:
            kwargs[max_tokens_key] = settings.default_max_tokens

        start_time = time.time()
        success = False
        error_type = None

        # Debug: log les paramètres envoyés
        logger.info(
            f"OpenAI API call: model={model}, "
            f"max_completion_tokens={kwargs.get('max_completion_tokens')}, "
            f"response_format={kwargs.get('response_format')}"
        )

        try:
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
                # Forcer content à chaîne vide si None
                content = content or ""

            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens

            success = True
            latency_ms = (time.time() - start_time) * 1000

            logger.info(
                f"OpenAI call réussi: {model} - {total_tokens} tokens - "
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
            logger.error(f"Erreur OpenAI call: {error_type} - {str(e)}")

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
