"""Classe abstraite pour les clients LLM.

Définit l'interface commune que tous les clients LLM doivent implémenter.
"""

from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Interface abstraite pour les clients LLM.

    Tous les clients (OpenAI, Anthropic, Mistral) doivent hériter de cette classe
    et implémenter la méthode call().
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
    async def call(
        self,
        messages: list[dict[str, str]],
        **kwargs,
    ) -> dict:
        """Effectue un appel au LLM de manière asynchrone.

        Args:
            messages: Liste de messages au format standard
                [{"role": "user/assistant/system", "content": "..."}]
            **kwargs: Paramètres additionnels (temperature, max_tokens, etc.)

        Returns:
            dict contenant:
                - content: str - Réponse du LLM
                - prompt_tokens: int - Tokens du prompt
                - completion_tokens: int - Tokens de la complétion
                - total_tokens: int - Total des tokens
                - model: str - Modèle utilisé

        Raises:
            Exception: En cas d'erreur API
        """
        pass
