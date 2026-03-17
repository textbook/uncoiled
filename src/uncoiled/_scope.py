"""Scope managers controlling component lifecycle."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ._types import Scope


@runtime_checkable
class ScopeManager(Protocol):
    """Protocol for custom scope implementations."""

    @property
    def scope(self) -> Scope:
        """Return the scope this manager handles."""
        ...

    def get[T](self, key: type[T], qualifier: str | None = None) -> T | None:
        """Return a cached instance or None."""
        ...

    def put[T](self, key: type[T], instance: T, qualifier: str | None = None) -> None:
        """Store an instance in this scope."""
        ...

    def clear(self) -> None:
        """Remove all instances from this scope."""
        ...


class SingletonScope:
    """Scope that caches a single instance per type for the container's lifetime."""

    def __init__(self) -> None:
        self._instances: dict[tuple[type, str | None], object] = {}

    @property
    def scope(self) -> Scope:
        """Return the scope type."""
        return Scope.SINGLETON

    def get[T](self, key: type[T], qualifier: str | None = None) -> T | None:
        """Return the cached instance or None."""
        return self._instances.get((key, qualifier))  # type: ignore[return-value]

    def put[T](self, key: type[T], instance: T, qualifier: str | None = None) -> None:
        """Cache the instance."""
        self._instances[(key, qualifier)] = instance

    def clear(self) -> None:
        """Remove all cached instances."""
        self._instances.clear()


class TransientScope:
    """Scope that never caches — creates a new instance on every resolution."""

    @property
    def scope(self) -> Scope:
        """Return the scope type."""
        return Scope.TRANSIENT

    def get[T](
        self,
        key: type[T],  # noqa: ARG002
        qualifier: str | None = None,  # noqa: ARG002
    ) -> T | None:
        """Return None; transient instances are never cached."""
        return None

    def put[T](
        self,
        key: type[T],
        instance: T,
        qualifier: str | None = None,
    ) -> None:
        """Do nothing; transient instances are not cached."""

    def clear(self) -> None:
        """No-op (nothing to clear)."""
