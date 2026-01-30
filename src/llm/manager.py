"""Manager LLM avec retry, rate limiting et batch processing.

Orchestration des appels LLM avec gestion des erreurs et parallélisation.
"""

import asyncio
import logging
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.llm.base import LLMClient
from src.llm.clients.anthropic import AnthropicClient
from src.llm.clients.mistral import MistralClient
from src.llm.clients.openai import OpenAIClient
from src.llm.config import settings
from src.llm.metrics import metrics_collector
from src.llm.rate_limiter import get_shared_rate_limiter
from src.utils.async_helpers import run_async_in_sync_context

logger = logging.getLogger(__name__)

# Registry des clients LLM - ajouter un nouveau provider = 1 ligne
CLIENT_REGISTRY: dict[str, type[LLMClient]] = {
    "openai": OpenAIClient,
    "anthropic": AnthropicClient,
    "mistral": MistralClient,
}


class LLMManager:
    """Gestionnaire centralisé pour les appels LLM.

    Features:
    - Retry automatique avec backoff exponentiel
    - Rate limiting par provider
    - Batch processing avec parallélisation contrôlée
    - Wrappers synchrones pour notebooks/scripts
    """

    def __init__(self):
        """Initialise le manager avec les clients et rate limiters partagés."""
        # Clients LLM (lazy initialization via registry)
        self._clients: dict[str, LLMClient] = {}

        # Rate limiters PARTAGÉS globalement (singleton par provider)
        self.rate_limiters = {
            "openai": get_shared_rate_limiter("openai", rpm=settings.openai_rpm),
            "anthropic": get_shared_rate_limiter(
                "anthropic", rpm=settings.anthropic_rpm
            ),
            "mistral": get_shared_rate_limiter("mistral", rpm=settings.mistral_rpm),
        }

        logger.info("LLMManager initialisé avec rate limiters partagés")

    def _get_client(self, provider: str) -> LLMClient:
        """Retourne le client pour un provider (lazy init via registry).

        Args:
            provider: Nom du provider (openai, anthropic, mistral)

        Returns:
            Instance du client LLM

        Raises:
            ValueError: Si le provider n'est pas dans le registry
        """
        provider_lower = provider.lower()

        if provider_lower not in CLIENT_REGISTRY:
            available = list(CLIENT_REGISTRY.keys())
            raise ValueError(
                f"Provider '{provider}' non implémenté. Disponibles: {available}"
            )

        if provider_lower not in self._clients:
            client_class = CLIENT_REGISTRY[provider_lower]
            self._clients[provider_lower] = client_class()
            logger.debug(f"Client {provider_lower} initialisé")

        return self._clients[provider_lower]

    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=settings.backoff_factor, min=1, max=60),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True,
    )
    async def call(
        self,
        provider: str,
        messages: list[dict[str, str]],
        model: str | None = None,
        **kwargs,
    ) -> dict:
        """Effectue un appel LLM avec retry et rate limiting.

        Args:
            provider: Provider à utiliser (openai/anthropic/mistral)
            messages: Messages à envoyer
            model: Modèle spécifique (optionnel, sinon utilise défaut du provider)
            **kwargs: Paramètres additionnels (temperature, max_tokens, etc.)

        Returns:
            dict avec content, tokens, model

        Raises:
            ValueError: Si provider inconnu
            Exception: En cas d'erreur API persistante
        """
        provider_lower = provider.lower()

        # Sélection du client via registry
        client = self._get_client(provider_lower)

        # Rate limiting : attendre jusqu'à pouvoir faire la requête
        await self.rate_limiters[provider_lower].acquire()

        logger.debug(f"Appel LLM: {provider_lower}/{model or 'default'}")

        # Override du modèle si fourni
        if model:
            kwargs["model"] = model

        # Appel au client (retry géré par @retry decorator)
        result = await client.call(messages, **kwargs)

        return result

    async def batch_call(
        self,
        requests: list[dict[str, Any]],
        max_concurrent: int = 20,
    ) -> list[dict]:
        """Effectue plusieurs appels LLM en parallèle.

        Args:
            requests: Liste de requêtes, chaque dict contient:
                - provider: str
                - messages: list[dict]
                - model: str (optionnel)
                - autres kwargs
            max_concurrent: Nombre max d'appels simultanés

        Returns:
            Liste de résultats (même ordre que requests)
            En cas d'erreur individuelle, le dict contient {"error": str}
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _call_with_semaphore(request: dict) -> dict:
            """Wrapper pour appeler call() avec semaphore global de concurrence."""
            async with semaphore:
                try:
                    # Extraire les paramètres requis
                    provider = request.pop("provider")
                    messages = request.pop("messages")

                    # Filtrer les métadonnées internes (clés commençant par _)
                    # Elles sont utilisées pour le post-processing mais ne doivent pas être passées aux APIs
                    llm_kwargs = {
                        k: v for k, v in request.items() if not k.startswith("_")
                    }

                    # Appel avec rate limiting automatique
                    return await self.call(provider, messages, **llm_kwargs)
                except Exception as e:
                    logger.error(f"Erreur batch call: {type(e).__name__} - {str(e)}")
                    return {"error": str(e), "error_type": type(e).__name__}

        # Lancer tous les appels en parallèle
        tasks = [_call_with_semaphore(req.copy()) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        logger.info(
            f"Batch call terminé: {len(results)} requêtes "
            f"({sum(1 for r in results if 'error' not in r)} succès)"
        )

        return results

    # ========== Appels avec parsing JSON automatique ==========

    async def call_with_json_parsing(
        self,
        provider: str,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_retries: int = 3,
        context_name: str = "document",
        **kwargs,
    ) -> tuple[dict, dict]:
        """Effectue un appel LLM avec retry automatique et parsing JSON robuste.

        Cette méthode encapsule :
        - Préparation des kwargs selon le provider (response_format pour OpenAI/Mistral)
        - Boucle de retry en cas d'erreur de parsing JSON
        - Extraction du JSON depuis markdown (gestion des délimiteurs ```json```)
        - Parsing avec json.loads()
        - Logging détaillé des erreurs

        Args:
            provider: Provider à utiliser
            messages: Messages à envoyer
            model: Modèle spécifique (optionnel)
            max_retries: Nombre max de tentatives en cas d'erreur JSON (défaut: 3)
            context_name: Nom pour le contexte des logs (ex: nom du fichier)
            **kwargs: Paramètres additionnels (seront fusionnés avec config auto)

        Returns:
            tuple de (parsed_json, response_metadata)
            - parsed_json: dict parsé depuis la réponse JSON du LLM
            - response_metadata: dict avec model, tokens, retry_count, etc.

        Raises:
            RuntimeError: Si toutes les tentatives de parsing échouent
            Exception: Autres erreurs LLM
        """
        import json

        # Préparer kwargs selon le provider
        # OpenAI et Mistral supportent response_format pour forcer JSON valide
        provider_lower = provider.lower()
        llm_kwargs = dict(kwargs)  # Copie pour ne pas modifier l'original

        if provider_lower in ["openai", "mistral"]:
            # Ajouter response_format si pas déjà présent
            if "response_format" not in llm_kwargs:
                llm_kwargs["response_format"] = {"type": "json_object"}

        # Boucle de retry pour gérer les erreurs JSONDecodeError
        parsed_data = None
        last_error = None
        retry_count = 0

        for attempt in range(max_retries):
            retry_count = attempt + 1

            if attempt > 0:
                logger.warning(f"Retry {retry_count}/{max_retries} pour {context_name}")

            try:
                # Appel LLM (retry réseau déjà géré par @retry decorator)
                response = await self.call(
                    provider=provider, messages=messages, model=model, **llm_kwargs
                )

                # Extraire le contenu
                content = response.get("content", "")

                # Log pour debug si contenu vide
                if not content or content.strip() == "":
                    logger.warning(
                        f"[WARNING] Contenu vide retourné par le LLM pour {context_name}\n"
                        f"   Model: {response.get('model')}\n"
                        f"   Tokens: {response.get('total_tokens')}"
                    )

                # Extraire le JSON (au cas où le LLM ajoute du texte autour)
                # Cherche les délimiteurs ```json ... ```
                if "```json" in content:
                    start = content.find("```json") + 7
                    end = content.find("```", start)
                    json_str = content[start:end].strip()
                elif "```" in content:
                    start = content.find("```") + 3
                    end = content.find("```", start)
                    json_str = content[start:end].strip()
                else:
                    json_str = content.strip()

                # Parser le JSON
                parsed_data = json.loads(json_str)

                # Succès : sortir de la boucle
                if retry_count > 1:
                    logger.info(
                        f"Succès au retry {retry_count}/{max_retries} pour {context_name}"
                    )

                # Ajouter retry_count aux métadonnées
                response["retry_count"] = retry_count

                # Normalize token field names (different providers use different names)
                # prompt_tokens -> input_tokens, completion_tokens -> output_tokens
                if "prompt_tokens" in response and "input_tokens" not in response:
                    response["input_tokens"] = response["prompt_tokens"]
                if "completion_tokens" in response and "output_tokens" not in response:
                    response["output_tokens"] = response["completion_tokens"]

                return parsed_data, response

            except json.JSONDecodeError as e:
                # Sauvegarder l'erreur pour logging final si toutes les tentatives échouent
                last_error = e

                # Afficher plus de contexte autour de l'erreur
                if "content" in locals():
                    error_pos = e.pos if hasattr(e, "pos") else 0
                    context_start = max(0, error_pos - 200)
                    context_end = min(len(content), error_pos + 200)
                    context = content[context_start:context_end]

                    if attempt < max_retries - 1:
                        # Tentative intermédiaire : log warning
                        logger.warning(
                            f"[WARNING] Erreur parsing JSON (tentative {retry_count}/{max_retries}): {e}\n"
                            f"   Context: {context_name}\n"
                            f"   Position erreur: {error_pos}"
                        )
                    else:
                        # Dernière tentative : log error complet
                        logger.error(
                            f"[ERROR] Erreur parsing JSON après {max_retries} tentatives : {e}\n"
                            f"   Context: {context_name}\n"
                            f"   Taille contenu: {len(content)} chars\n"
                            f"   Position erreur: {error_pos}\n"
                            f"   Contexte (±200 chars):\n"
                            f"   >>> {context} <<<\n"
                            f"   Contenu complet (premières 2000 chars):\n"
                            f"   {content[:2000]}"
                        )

        # Si toutes les tentatives ont échoué
        logger.error(
            f"[ERROR] Échec définitif pour {context_name} après {max_retries} tentatives"
        )
        raise RuntimeError(
            f"JSON parsing failed after {max_retries} retries for {context_name}: {str(last_error)}"
        )

    # ========== Wrappers synchrones pour notebooks/scripts ==========

    def call_sync(
        self,
        provider: str,
        messages: list[dict[str, str]],
        model: str | None = None,
        **kwargs,
    ) -> dict:
        """Version synchrone de call().

        Détecte automatiquement le contexte (notebook vs script) et utilise
        la méthode appropriée pour exécuter l'appel async.

        Args:
            provider: Provider à utiliser
            messages: Messages à envoyer
            model: Modèle spécifique (optionnel)
            **kwargs: Paramètres additionnels

        Returns:
            dict avec content, tokens, model
        """
        return run_async_in_sync_context(self.call(provider, messages, model, **kwargs))

    def batch_call_sync(
        self,
        requests: list[dict[str, Any]],
        max_concurrent: int = 20,
    ) -> list[dict]:
        """Version synchrone de batch_call().

        Détecte automatiquement le contexte (notebook vs script).

        Args:
            requests: Liste de requêtes
            max_concurrent: Nombre max d'appels simultanés

        Returns:
            Liste de résultats
        """
        return run_async_in_sync_context(self.batch_call(requests, max_concurrent))

    def call_with_json_parsing_sync(
        self,
        provider: str,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_retries: int = 3,
        context_name: str = "document",
        **kwargs,
    ) -> tuple[dict, dict]:
        """Version synchrone de call_with_json_parsing().

        Détecte automatiquement le contexte (notebook vs script).

        Args:
            provider: Provider à utiliser
            messages: Messages à envoyer
            model: Modèle spécifique (optionnel)
            max_retries: Nombre max de tentatives en cas d'erreur JSON
            context_name: Nom pour le contexte des logs
            **kwargs: Paramètres additionnels

        Returns:
            tuple de (parsed_json, response_metadata)
        """
        return run_async_in_sync_context(
            self.call_with_json_parsing(
                provider, messages, model, max_retries, context_name, **kwargs
            )
        )

    # ========== Méthodes utilitaires ==========

    def export_metrics(self) -> None:
        """Exporte les métriques collectées vers DuckDB."""
        metrics_collector.export_to_duckdb()
        logger.info("Métriques exportées vers DuckDB")

    def get_metrics_summary(self) -> dict:
        """Retourne un résumé des métriques.

        Returns:
            dict avec stats par provider
        """
        return metrics_collector.get_summary()
