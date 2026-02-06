"""Custom exceptions for Chiron.

Provides a hierarchy of exceptions for different error types,
enabling precise error handling throughout the application.
"""


class ChironError(Exception):
    """Base exception for all Chiron errors.

    All custom exceptions inherit from this class, allowing
    catch-all handling when needed.
    """

    def __init__(self, message: str, details: dict | None = None) -> None:
        """Initialize exception with message and optional details.

        Args:
            message: Human-readable error description.
            details: Optional dict with additional context (file paths, values, etc.).
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class ParserError(ChironError):
    """PDF parsing failed.

    Raised when bulletin PDF cannot be parsed correctly:
    - File not found or corrupted
    - Unexpected format
    - Missing required fields
    """

    pass


class PrivacyError(ChironError):
    """Privacy/pseudonymization error.

    Raised when pseudonymization operations fail:
    - Mapping storage errors
    - Invalid pseudonym format
    - Depseudonymization without mapping
    """

    pass


class StorageError(ChironError):
    """Database operation failed.

    Raised when DuckDB operations fail:
    - Connection errors
    - Query failures
    - Constraint violations
    """

    pass


class GenerationError(ChironError):
    """LLM generation failed.

    Raised when synthesis generation fails:
    - LLM API errors
    - Invalid response format
    - JSON parsing failures
    """

    pass


class ConfigurationError(ChironError):
    """Configuration error.

    Raised when configuration is invalid:
    - Missing environment variables
    - Invalid settings values
    - Missing API keys
    """

    pass


class AnonymizationError(ChironError):
    """Anonymization failed.

    Raised when PDF anonymization fails and sending
    the original document to cloud would violate RGPD:
    - Name extraction failed
    - NER processing error
    - PDF redaction error
    """

    pass
