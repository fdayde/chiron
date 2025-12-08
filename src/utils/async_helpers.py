"""Helpers pour l'exécution de coroutines async depuis du code synchrone.

Ce module fournit des utilitaires pour gérer l'interface entre code sync et async,
notamment pour les notebooks Jupyter qui ont déjà un event loop actif en arrière plan.
"""

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


def run_async_in_sync_context[T](coro: Coroutine[Any, Any, T]) -> T:
    """Exécute une coroutine async depuis un contexte synchrone.

    Gère automatiquement le conflit d'event loop dans les notebooks Jupyter:
    - **Script Python**: Pas d'event loop → utilise asyncio.run() directement
    - **Notebook Jupyter**: Event loop déjà actif → nécessite nest_asyncio

    Les notebooks Jupyter ont un event loop qui tourne en arrière-plan pour
    l'interactivité. asyncio.run() essaie de créer un NOUVEAU loop, ce qui
    provoque l'erreur "cannot be called from a running event loop".
    nest_asyncio patche asyncio pour permettre l'imbrication de loops.

    Args:
        coro: Coroutine à exécuter

    Returns:
        Le résultat de la coroutine

    Raises:
        RuntimeError: Si nest_asyncio n'est pas installé dans un notebook

    Examples:
        >>> async def my_async_func():
        ...     await asyncio.sleep(1)
        ...     return "done"
        >>> result = run_async_in_sync_context(my_async_func())
        >>> print(result)
        done
    """
    try:
        # Essayer de récupérer un event loop existant
        asyncio.get_running_loop()

        # Un event loop existe déjà (cas des notebooks Jupyter)
        # On a besoin de nest_asyncio pour permettre asyncio.run() dans un loop existant
        try:
            import nest_asyncio

            nest_asyncio.apply()
        except ImportError as e:
            raise RuntimeError(
                "nest_asyncio est requis pour exécuter du code async dans un notebook Jupyter. "
                "Installez-le avec: pip install nest-asyncio"
            ) from e

        # Exécuter la coroutine
        return asyncio.run(coro)

    except RuntimeError:
        # Pas d'event loop existant (cas des scripts Python normaux)
        # On peut utiliser asyncio.run() directement
        return asyncio.run(coro)
