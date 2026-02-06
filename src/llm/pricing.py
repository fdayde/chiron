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


def estimate_synthese_cost(
    nb_eleves: int,
    avg_input_tokens: int = 2000,
    avg_output_tokens: int = 500,
    provider: str = "openai",
    model: str | None = None,
) -> dict:
    """Estime le coût de génération de synthèses pour N élèves.

    Args:
        nb_eleves: Nombre d'élèves à traiter.
        avg_input_tokens: Tokens moyens en input par élève (défaut: 2000).
        avg_output_tokens: Tokens moyens en output par élève (défaut: 500).
        provider: Provider LLM à utiliser.
        model: Modèle à utiliser (défaut: modèle par défaut du provider).

    Returns:
        Dict avec 'nb_eleves', 'total_tokens', 'cost_usd', 'cost_per_eleve'.
    """
    from src.llm.config import settings

    # Récupérer le modèle et pricing config
    try:
        model = model or settings.get_model(provider)
        pricing_config = settings.get_pricing(provider)
    except ValueError:
        return {"error": f"Provider inconnu: {provider}"}

    calculator = PricingCalculator(provider, pricing_config)

    # Calculer pour un élève
    cost_per_eleve = calculator.calculate(model, avg_input_tokens, avg_output_tokens)
    total_cost = cost_per_eleve * nb_eleves
    total_tokens = (avg_input_tokens + avg_output_tokens) * nb_eleves

    return {
        "nb_eleves": nb_eleves,
        "provider": provider,
        "model": model,
        "avg_input_tokens": avg_input_tokens,
        "avg_output_tokens": avg_output_tokens,
        "total_tokens": total_tokens,
        "cost_per_eleve": round(cost_per_eleve, 6),
        "cost_usd": round(total_cost, 4),
    }
