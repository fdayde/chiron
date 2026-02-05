"""Client Anthropic avec gestion des métriques.

Supporte les modèles Claude (Sonnet 4.5, Haiku 3.5).
"""

import logging
import time

from anthropic import AsyncAnthropic

from src.llm.base import LLMClient
from src.llm.config import settings
from src.llm.metrics import LLMCallMetrics, metrics_collector
from src.llm.pricing import PricingCalculator

logger = logging.getLogger(__name__)


class AnthropicClient(LLMClient):
    """Client pour les modèles Anthropic (Claude Sonnet 4.5, Haiku 3.5)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        """Initialise le client Anthropic.

        Args:
            api_key: Clé API Anthropic. Si None, utilise settings.anthropic_api_key
            model: Nom du modèle. Si None, utilise settings.get_model("anthropic")
        """
        self._api_key = api_key or settings.anthropic_api_key
        self._model = model or settings.get_model("anthropic")
        self._client = AsyncAnthropic(api_key=self._api_key)
        self.pricing_calc = PricingCalculator("anthropic", settings.anthropic_pricing)
        logger.info(f"AnthropicClient initialisé avec modèle: {self._model}")

    @property
    def provider_name(self) -> str:
        """Retourne le nom du provider."""
        return "anthropic"

    @property
    def model_name(self) -> str:
        """Retourne le nom du modèle."""
        return self._model

    def _get_max_tokens_for_model(self, model: str) -> int:
        """Retourne le max_tokens approprié selon le modèle.

        Args:
            model: Nom du modèle

        Returns:
            Limite max_tokens pour ce modèle
        """
        # Haiku 3.5 a une limite de 8192 tokens
        if "haiku" in model.lower():
            return 8192
        # Sonnet 4.5 et autres ont 16384
        return 16384

    def _prepare_messages(
        self, messages: list[dict[str, str]]
    ) -> tuple[str | None, list[dict[str, str]]]:
        """Sépare les messages system des autres pour l'API Anthropic.

        L'API Anthropic requiert que les messages system soient passés
        dans un paramètre séparé au lieu d'être dans la liste des messages.

        Args:
            messages: Liste de messages au format standard

        Returns:
            Tuple (system_prompt, filtered_messages)
            - system_prompt: Contenu concaténé des messages system (None si aucun)
            - filtered_messages: Messages sans les messages system
        """
        system_messages = [m["content"] for m in messages if m["role"] == "system"]
        other_messages = [m for m in messages if m["role"] != "system"]

        system_prompt = "\n\n".join(system_messages) if system_messages else None
        return system_prompt, other_messages

    async def call(
        self,
        messages: list[dict[str, str]],
        **kwargs,
    ) -> dict:
        """Effectue un appel à l'API Anthropic.

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

        # Séparer les messages system
        system_prompt, filtered_messages = self._prepare_messages(messages)

        # Paramètres par défaut
        if "temperature" not in kwargs:
            kwargs["temperature"] = settings.default_temperature

        if "max_tokens" not in kwargs:
            # Utiliser la limite appropriée selon le modèle
            kwargs["max_tokens"] = self._get_max_tokens_for_model(model)

        start_time = time.time()
        success = False
        error_type = None

        try:
            # Construire les paramètres de l'appel
            call_params = {
                "model": model,
                "messages": filtered_messages,
                **kwargs,
            }

            # Ajouter system prompt si présent
            if system_prompt:
                call_params["system"] = system_prompt

            # Appel API
            response = await self._client.messages.create(**call_params)

            # Extraire les données
            # L'API Anthropic retourne response.content qui est une liste de blocks
            content_blocks = response.content
            if content_blocks and len(content_blocks) > 0:
                # Concaténer tous les text blocks
                content = "".join(
                    block.text for block in content_blocks if hasattr(block, "text")
                )
            else:
                content = ""

            # Debug: vérifier si content est vide
            if not content or content.strip() == "":
                logger.warning(
                    f"[WARNING] Anthropic retourné content vide pour {model}\n"
                    f"   Content blocks: {content_blocks}\n"
                    f"   Stop reason: {response.stop_reason}"
                )
                content = content or ""

            # Extraire les tokens depuis usage
            prompt_tokens = response.usage.input_tokens
            completion_tokens = response.usage.output_tokens
            total_tokens = prompt_tokens + completion_tokens

            # Utiliser le nom de modèle retourné par l'API (plus fiable pour pricing)
            actual_model = response.model

            success = True
            latency_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Anthropic call réussi: {actual_model} - {total_tokens} tokens - "
                f"{latency_ms:.0f}ms - Content length: {len(content)} chars"
            )

            # Calculer le coût
            cost_usd = self.pricing_calc.calculate(
                actual_model, prompt_tokens, completion_tokens
            )

            # Collecter métriques
            metric = LLMCallMetrics(
                provider=self.provider_name,
                model=actual_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                success=success,
                error_type=None,
                cost_usd=cost_usd,
            )
            metrics_collector.collect(metric)

            return {
                "content": content,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "model": actual_model,
                "cost_usd": cost_usd,
            }

        except Exception as e:
            error_type = type(e).__name__
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"Erreur Anthropic call: {error_type} - {str(e)}")

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
