"""Client Anthropic avec gestion des métriques.

Supporte les modèles Claude (Sonnet 4.5, Haiku 3.5).
"""

import logging

from anthropic import AsyncAnthropic

from src.llm.base import LLMClient, LLMRawResponse
from src.llm.config import settings
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
        """
        system_messages = [m["content"] for m in messages if m["role"] == "system"]
        other_messages = [m for m in messages if m["role"] != "system"]

        system_prompt = "\n\n".join(system_messages) if system_messages else None
        return system_prompt, other_messages

    async def _do_call(
        self,
        messages: list[dict[str, str]],
        model: str,
        **kwargs,
    ) -> LLMRawResponse:
        """Effectue l'appel à l'API Anthropic.

        Gère la séparation des messages system et l'extraction des content blocks.
        """
        # Séparer les messages system
        system_prompt, filtered_messages = self._prepare_messages(messages)

        # Paramètres par défaut
        if "temperature" not in kwargs:
            kwargs["temperature"] = settings.default_temperature

        if "max_tokens" not in kwargs:
            kwargs["max_tokens"] = self._get_max_tokens_for_model(model)

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

        # Extraire les données — l'API retourne une liste de content blocks
        content_blocks = response.content
        if content_blocks and len(content_blocks) > 0:
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

        # Extraire les tokens (noms différents chez Anthropic)
        prompt_tokens = response.usage.input_tokens
        completion_tokens = response.usage.output_tokens

        return LLMRawResponse(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model=response.model,  # Modèle réel retourné par l'API
        )
