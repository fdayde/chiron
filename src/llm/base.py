"""Classe abstraite pour les clients LLM.

Définit l'interface commune que tous les clients LLM doivent implémenter.
La méthode call() fournit le boilerplate commun (timing, métriques, coût).
Chaque sous-classe implémente _do_call() avec sa logique spécifique.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.llm.metrics import LLMCallMetrics, metrics_collector

logger = logging.getLogger(__name__)


@dataclass
class LLMRawResponse:
    """Résultat brut d'un appel API LLM, retourné par _do_call()."""

    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str


class LLMClient(ABC):
    """Interface abstraite pour les clients LLM.

    Tous les clients (OpenAI, Anthropic, Mistral) doivent hériter de cette classe
    et implémenter _do_call().

    Attributs attendus dans les sous-classes :
        _model: str — Nom du modèle par défaut.
        pricing_calc: PricingCalculator — Calculateur de coût.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Nom du provider (openai/anthropic/mistral)."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Nom du modèle utilisé."""
        pass

    @abstractmethod
    async def _do_call(
        self,
        messages: list[dict[str, str]],
        model: str,
        **kwargs,
    ) -> LLMRawResponse:
        """Effectue l'appel API spécifique au provider.

        Args:
            messages: Liste de messages au format standard.
            model: Modèle à utiliser (déjà résolu depuis kwargs).
            **kwargs: Paramètres additionnels (temperature, max_tokens, etc.)

        Returns:
            LLMRawResponse avec le contenu et les compteurs de tokens.

        Raises:
            Exception: En cas d'erreur API.
        """
        pass

    async def call(
        self,
        messages: list[dict[str, str]],
        **kwargs,
    ) -> dict:
        """Effectue un appel au LLM avec timing, métriques et coût.

        Args:
            messages: Liste de messages au format standard
                [{"role": "user/assistant/system", "content": "..."}]
            **kwargs: Paramètres additionnels (temperature, max_tokens, model, etc.)

        Returns:
            dict contenant:
                - content: str - Réponse du LLM
                - prompt_tokens: int - Tokens du prompt
                - completion_tokens: int - Tokens de la complétion
                - total_tokens: int - Total des tokens
                - model: str - Modèle utilisé
                - cost_usd: float - Coût estimé en USD
        """
        model = kwargs.pop("model", self.model_name)
        start_time = time.time()

        try:
            raw = await self._do_call(messages, model, **kwargs)
            latency_ms = (time.time() - start_time) * 1000

            cost_usd = self.pricing_calc.calculate(
                raw.model, raw.prompt_tokens, raw.completion_tokens
            )

            logger.info(
                f"{self.provider_name} call réussi: {raw.model} - {raw.total_tokens} tokens - "
                f"{latency_ms:.0f}ms - Content length: {len(raw.content)} chars"
            )

            metrics_collector.collect(
                LLMCallMetrics(
                    provider=self.provider_name,
                    model=raw.model,
                    prompt_tokens=raw.prompt_tokens,
                    completion_tokens=raw.completion_tokens,
                    total_tokens=raw.total_tokens,
                    latency_ms=latency_ms,
                    success=True,
                    error_type=None,
                    cost_usd=cost_usd,
                )
            )

            return {
                "content": raw.content,
                "prompt_tokens": raw.prompt_tokens,
                "completion_tokens": raw.completion_tokens,
                "total_tokens": raw.total_tokens,
                "model": raw.model,
                "cost_usd": cost_usd,
            }

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_type = type(e).__name__
            logger.error(f"Erreur {self.provider_name} call: {error_type} - {str(e)}")

            metrics_collector.collect(
                LLMCallMetrics(
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
            )

            raise
