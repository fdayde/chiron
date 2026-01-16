"""Base repository interface."""

from abc import ABC, abstractmethod
from typing import TypeVar

T = TypeVar("T")


class Repository[T](ABC):
    """Abstract base repository defining standard CRUD operations.

    All repositories should implement these methods for consistent
    data access patterns across the application.
    """

    @abstractmethod
    def create(self, entity: T) -> str:
        """Create a new entity.

        Args:
            entity: Entity to create.

        Returns:
            ID of created entity.
        """
        ...

    @abstractmethod
    def get(self, entity_id: str) -> T | None:
        """Get an entity by ID.

        Args:
            entity_id: Entity identifier.

        Returns:
            Entity or None if not found.
        """
        ...

    @abstractmethod
    def list(self, **filters) -> list[T]:
        """List entities with optional filters.

        Args:
            **filters: Key-value filters.

        Returns:
            List of matching entities.
        """
        ...

    @abstractmethod
    def update(self, entity_id: str, **updates) -> bool:
        """Update an entity.

        Args:
            entity_id: Entity identifier.
            **updates: Fields to update.

        Returns:
            True if updated, False if not found.
        """
        ...

    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        """Delete an entity.

        Args:
            entity_id: Entity identifier.

        Returns:
            True if deleted, False if not found.
        """
        ...
