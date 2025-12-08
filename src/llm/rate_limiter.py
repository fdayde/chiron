"""Rate limiters pour contrôler le débit d'appels aux APIs LLM.

Ce module implémente des rate limiters basés sur fenêtre glissante
pour respecter les limites API (RPM, TPM) de chaque provider.

Les rate limiters sont partagés globalement (singleton) pour garantir
un vrai rate limiting au niveau de l'application.
"""

import asyncio
import logging
import time

logger = logging.getLogger(__name__)

# Stockage global des rate limiters (singleton par provider)
_GLOBAL_RATE_LIMITERS: dict[str, "SimpleRateLimiter"] = {}


class SimpleRateLimiter:
    """Rate limiter basé sur RPM avec fenêtre glissante de 60 secondes.

    Garantit qu'on ne dépasse jamais le nombre de requêtes par minute (RPM)
    spécifié, en utilisant une fenêtre glissante pour un contrôle précis.

    Attributes:
        rpm: Nombre max de requêtes par minute
        requests: Liste des timestamps des requêtes dans la fenêtre glissante
        lock: Lock asyncio pour thread-safety
        verbose: Si True, affiche les messages de rate limiting sur stdout (notebooks)
    """

    def __init__(self, rpm: int, verbose: bool = True):
        """Initialise le rate limiter.

        Args:
            rpm: Nombre maximum de requêtes par minute
            verbose: Si True, affiche les messages dans stdout (pratique pour notebooks)
        """
        self.rpm = rpm
        self.verbose = verbose
        self.requests: list[float] = []  # timestamps des requêtes
        self.lock = asyncio.Lock()

        logger.info(f"SimpleRateLimiter initialisé: {rpm} RPM (verbose={verbose})")

    async def acquire(self, timeout: float | None = None) -> None:
        """Attend jusqu'à pouvoir faire une requête sans dépasser le RPM.

        Cette méthode bloque si le nombre de requêtes dans la fenêtre de 60s
        atteint ou dépasse le RPM configuré. Elle attend jusqu'à ce qu'une
        requête expire de la fenêtre glissante.

        Args:
            timeout: Temps max d'attente en secondes (None = pas de limite)

        Raises:
            asyncio.TimeoutError: Si le timeout est dépassé
            asyncio.CancelledError: Si la tâche est annulée pendant l'attente

        Note:
            - Thread-safe grâce au lock asyncio
            - En cas de cancellation, le lock est correctement libéré
            - L'exception CancelledError est loggée puis propagée
        """

        async def _acquire_with_lock():
            try:
                async with self.lock:
                    while True:  # Boucle au lieu de récursion (évite deadlock)
                        now = time.monotonic()

                        # 1. Nettoyer les requêtes qui sont sorties de la fenêtre de 60s
                        self.requests = [ts for ts in self.requests if now - ts < 60]

                        # 2. Vérifier si on peut faire la requête
                        if len(self.requests) >= self.rpm:
                            # On a atteint la limite, il faut attendre
                            oldest = self.requests[0]
                            wait_time = (
                                60 - (now - oldest) + 0.1
                            )  # +0.1s marge de sécurité

                            msg = (
                                f"⏳ Rate limit atteint ({self.rpm} RPM): "
                                f"attente de {wait_time:.1f}s "
                                f"({len(self.requests)} requêtes dans la fenêtre)"
                            )
                            logger.info(msg)
                            if self.verbose:
                                print(msg)

                            await asyncio.sleep(wait_time)

                            # Message après l'attente
                            msg_resume = "✅ Attente terminée, reprise des requêtes (fenêtre libérée)"
                            logger.info(msg_resume)
                            if self.verbose:
                                print(msg_resume)

                            # La boucle va réessayer automatiquement
                        else:
                            # 3. OK, on peut faire la requête
                            self.requests.append(now)

                            # Log pour debug (seulement tous les 10 appels pour éviter spam)
                            if len(self.requests) % 10 == 0:
                                logger.debug(
                                    f"Rate limiter: {len(self.requests)}/{self.rpm} requêtes "
                                    f"dans la fenêtre de 60s"
                                )

                            # Sortir de la boucle
                            break
            except asyncio.CancelledError:
                # La tâche a été annulée (via task.cancel() ou timeout global)
                logger.info(
                    f"Rate limiter: acquisition annulée "
                    f"({len(self.requests)}/{self.rpm} requêtes actives)"
                )
                # Re-raise pour propager la cancellation
                raise

        # Appliquer le timeout si spécifié
        if timeout:
            try:
                async with asyncio.timeout(timeout):
                    await _acquire_with_lock()
            except TimeoutError:
                logger.warning(
                    f"Timeout atteint ({timeout}s) en attendant le rate limiter"
                )
                raise TimeoutError(
                    f"Rate limiter timeout après {timeout}s d'attente"
                ) from None
        else:
            await _acquire_with_lock()

    def get_current_usage(self) -> dict[str, int | float]:
        """Retourne l'usage actuel du rate limiter.

        Returns:
            dict avec:
                - current_requests: Nombre de requêtes dans la fenêtre
                - rpm_limit: Limite RPM configurée
                - available_slots: Slots disponibles
                - usage_percent: Pourcentage d'utilisation

        Note:
            Cette méthode n'est pas thread-safe et est destinée au monitoring.
        """
        now = time.monotonic()
        active_requests = [ts for ts in self.requests if now - ts < 60]
        available = max(0, self.rpm - len(active_requests))
        usage_pct = (len(active_requests) / self.rpm) * 100 if self.rpm > 0 else 0

        return {
            "current_requests": len(active_requests),
            "rpm_limit": self.rpm,
            "available_slots": available,
            "usage_percent": round(usage_pct, 1),
        }

    def reset(self) -> None:
        """Reset le rate limiter (vide la fenêtre glissante).

        Utile pour les tests ou après un changement de configuration.
        """
        self.requests.clear()
        logger.info(f"Rate limiter reset: {self.rpm} RPM (verbose={self.verbose})")


# ============================================================================
# FONCTION HELPER POUR RATE LIMITERS PARTAGÉS (SINGLETON)
# ============================================================================


def get_shared_rate_limiter(
    provider: str, rpm: int, verbose: bool = True
) -> SimpleRateLimiter:
    """Retourne le rate limiter partagé pour un provider (singleton).

    Cette fonction garantit qu'il n'y a qu'une seule instance de rate limiter
    par provider dans toute l'application. Cela permet un vrai rate limiting
    global plutôt que par instance de LLMManager.

    Args:
        provider: Nom du provider (openai, anthropic, mistral)
        rpm: Nombre maximum de requêtes par minute
        verbose: Si True, affiche les messages de rate limiting

    Returns:
        Instance partagée du rate limiter pour ce provider

    Example:
        >>> limiter1 = get_shared_rate_limiter("openai", 500)
        >>> limiter2 = get_shared_rate_limiter("openai", 500)
        >>> limiter1 is limiter2  # True : même instance
    """
    if provider not in _GLOBAL_RATE_LIMITERS:
        # Créer le rate limiter pour ce provider
        _GLOBAL_RATE_LIMITERS[provider] = SimpleRateLimiter(rpm=rpm, verbose=verbose)
        logger.info(
            f"✨ Rate limiter PARTAGÉ créé pour {provider}: {rpm} RPM (singleton)"
        )
    else:
        # Déjà existant, ne pas recréer
        logger.debug(f"Réutilisation du rate limiter partagé existant pour {provider}")

    return _GLOBAL_RATE_LIMITERS[provider]


def reset_all_rate_limiters() -> None:
    """Reset tous les rate limiters partagés.

    Utile pour les tests ou pour réinitialiser l'état global.
    """
    for provider, limiter in _GLOBAL_RATE_LIMITERS.items():
        limiter.reset()
        logger.info(f"Rate limiter partagé reset pour {provider}")


def get_all_rate_limiters_status() -> dict[str, dict]:
    """Retourne le statut de tous les rate limiters actifs.

    Returns:
        dict avec status de chaque provider
    """
    return {
        provider: limiter.get_current_usage()
        for provider, limiter in _GLOBAL_RATE_LIMITERS.items()
    }
