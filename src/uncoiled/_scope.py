"""Scope managers controlling component lifecycle."""

from __future__ import annotations

import contextlib
import contextvars
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ._types import Scope

if TYPE_CHECKING:
    from collections.abc import Iterator


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

    def remove(self, key: type, qualifier: str | None = None) -> None:
        """Remove a single cached instance."""
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

    def remove(self, key: type, qualifier: str | None = None) -> None:
        """Remove a cached instance."""
        self._instances.pop((key, qualifier), None)

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

    def remove(
        self,
        key: type,
        qualifier: str | None = None,
    ) -> None:
        """No-op (nothing to remove)."""

    def clear(self) -> None:
        """No-op (nothing to clear)."""


class RequestScope:
    """Scope that caches instances per request context via contextvars."""

    def __init__(self) -> None:
        self._var: contextvars.ContextVar[dict[tuple[type, str | None], object]] = (
            contextvars.ContextVar("_uncoiled_request_scope")
        )

    @property
    def scope(self) -> Scope:
        """Return the scope type."""
        return Scope.REQUEST

    def get[T](self, key: type[T], qualifier: str | None = None) -> T | None:
        """Return the cached instance for the current context, or None."""
        instances = self._var.get(None)
        if instances is None:
            return None
        return instances.get((key, qualifier))  # type: ignore[return-value]

    def put[T](self, key: type[T], instance: T, qualifier: str | None = None) -> None:
        """Cache the instance in the current request context."""
        instances = self._var.get(None)
        if instances is None:
            msg = "No active request context"
            raise LookupError(msg)
        instances[(key, qualifier)] = instance

    def remove(self, key: type, qualifier: str | None = None) -> None:
        """Remove a cached instance from the current context."""
        instances = self._var.get(None)
        if instances is not None:
            instances.pop((key, qualifier), None)

    def clear(self) -> None:
        """Clear all instances in the current context."""
        instances = self._var.get(None)
        if instances is not None:
            instances.clear()

    @contextlib.contextmanager
    def context(self) -> Iterator[None]:
        """Enter a new request context."""
        token = self._var.set({})
        try:
            yield
        finally:
            self._var.reset(token)
