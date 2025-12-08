"""Calcul centralisé des coûts LLM par provider.

Unifie la logique de pricing pour tous les providers (OpenAI, Anthropic, Mistral).
Élimine la duplication de _calculate_cost() dans chaque client.
"""

import logging
import re

logger = logging.getLogger(__name__)


class PricingCalculator:
    """Calculateur de coûts unifié pour tous les providers.

    Gère les variantes de noms de modèles et les fallbacks intelligents.
    """

    def __init__(self, provider: str, pricing_config: dict[str, tuple[float, float]]):
        """Initialise le calculateur de coûts.

        Args:
            provider: Nom du provider (openai, anthropic, mistral)
            pricing_config: Dict {model: (input_price_per_1M, output_price_per_1M)}
        """
        self.provider = provider
        self.pricing = pricing_config

    def calculate(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        """Calcule le coût en USD d'un appel LLM.

        Args:
            model: Nom du modèle (peut contenir date/version)
            prompt_tokens: Nombre de tokens d'input
            completion_tokens: Nombre de tokens d'output

        Returns:
            Coût en USD (arrondi à 6 décimales)
        """
        price = self._find_price(model)
        if price is None:
            logger.warning(
                f"[{self.provider}] Pricing inconnu pour modèle '{model}', "
                f"coût retourné: $0.00"
            )
            return 0.0

        input_price, output_price = price
        cost = (prompt_tokens * input_price / 1_000_000) + (
            completion_tokens * output_price / 1_000_000
        )
        return round(cost, 6)

    def _find_price(self, model: str) -> tuple[float, float] | None:
        """Recherche intelligente du pricing selon le provider.

        Gère les variantes de noms de modèles :
        - Anthropic : strip suffix YYYYMMDD (claude-haiku-4-5-20251001 → claude-haiku-4-5)
        - OpenAI : essaie nom complet, base, base+variant
        - Mistral : lookup direct

        Args:
            model: Nom du modèle

        Returns:
            Tuple (input_price, output_price) ou None si non trouvé
        """
        if self.provider == "anthropic":
            # Strip YYYYMMDD suffix
            model_base = re.sub(r"-\d{8}$", "", model)
            return self.pricing.get(model_base)

        elif self.provider == "openai":
            # Essayer plusieurs variantes
            variants = [
                model,  # Nom complet (ex: "gpt-4.1-mini-2024-09-12")
                "-".join(model.split("-")[:2]),  # Base (ex: "gpt-4.1")
                "-".join(model.split("-")[:3]),  # Base + variant (ex: "gpt-4.1-mini")
            ]
            for variant in variants:
                if variant in self.pricing:
                    return self.pricing[variant]
            return None

        else:  # mistral
            return self.pricing.get(model)


def calculate_batch_cost(
    tokens: dict[str, int],
    model_overrides: dict[str, str] | None = None,
) -> float:
    """Calcule le coût total d'un batch selon les tokens utilisés par provider.

    Utilise les tarifs définis dans settings pour calculer le coût précis.
    Pour chaque provider, utilise le modèle spécifié dans model_overrides ou le default.

    Args:
        tokens: Dict des tokens par provider, ex: {"openai": 50000, "mistral": 30000, "anthropic": 20000}
        model_overrides: Dict optionnel pour spécifier les modèles utilisés, ex: {"anthropic": "claude-sonnet-4-5"}

    Returns:
        Coût total en USD (arrondi à 2 décimales)

    Example:
        >>> tokens = {"openai": 100000, "anthropic": 50000}
        >>> cost = calculate_batch_cost(tokens)
        >>> print(f"Coût total: ${cost:.2f}")
    """
    from src.llm.config import settings

    model_overrides = model_overrides or {}
    total_cost = 0.0

    # Calculer le coût pour chaque provider
    for provider, token_count in tokens.items():
        if token_count == 0:
            continue

        # Déterminer le modèle utilisé (override ou default)
        model = model_overrides.get(provider) or settings.get_model(provider)

        # Récupérer le pricing config pour ce provider
        if provider == "openai":
            pricing_config = settings.openai_pricing
        elif provider == "anthropic":
            pricing_config = settings.anthropic_pricing
        elif provider == "mistral":
            pricing_config = settings.mistral_pricing
        else:
            logger.warning(
                f"Provider inconnu '{provider}', coût ignoré pour {token_count} tokens"
            )
            continue

        # Créer calculateur et calculer le coût
        calculator = PricingCalculator(provider=provider, pricing_config=pricing_config)

        # Pour un batch, on approxime 40% input / 60% output (ratio typique extraction)
        # Note: c'est une approximation, le coût réel dépend du ratio input/output réel
        input_tokens = int(token_count * 0.4)
        output_tokens = int(token_count * 0.6)

        cost = calculator.calculate(
            model=model, prompt_tokens=input_tokens, completion_tokens=output_tokens
        )
        total_cost += cost

        logger.debug(f"[{provider}] {token_count:,} tokens ({model}) = ${cost:.4f}")

    return round(total_cost, 2)
