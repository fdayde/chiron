"""Exceptions personnalisées pour Chiron.

Hiérarchie d'exceptions pour une gestion d'erreurs précise.
"""


class ChironError(Exception):
    """Exception de base pour toutes les erreurs Chiron."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        """Initialise l'exception.

        Args:
            message: Description de l'erreur.
            details: Contexte additionnel optionnel (chemins, valeurs, etc.).
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class ParserError(ChironError):
    """Échec du parsing PDF (fichier corrompu, format inattendu, champs manquants)."""

    pass


class PrivacyError(ChironError):
    """Erreur de pseudonymisation (mapping, format, dépseudonymisation)."""

    pass


class StorageError(ChironError):
    """Échec d'opération base de données (connexion, requête, contrainte)."""

    pass


class GenerationError(ChironError):
    """Échec de génération LLM (erreur API, format réponse, parsing JSON)."""

    pass


class ConfigurationError(ChironError):
    """Erreur de configuration (variable d'environnement, clé API manquante)."""

    pass


class AnonymizationError(ChironError):
    """Échec d'anonymisation PDF (NER, rédaction). Envoi cloud interdit (RGPD)."""

    pass
