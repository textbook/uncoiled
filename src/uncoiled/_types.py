"""Core types for the uncoiled dependency injection framework."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable


class Scope(enum.Enum):
    """Lifecycle scope for a component."""

    SINGLETON = "singleton"
    TRANSIENT = "transient"
    REQUEST = "request"


type Factory[T] = Callable[..., T]
"""A callable that produces an instance of type T."""


class _MissingType:
    def __repr__(self) -> str:
        return "<MISSING>"


MISSING = _MissingType()
"""Sentinel value indicating no value was provided."""


@runtime_checkable
class Disposable(Protocol):
    """Protocol for components that need cleanup on container close."""

    def close(self) -> None:
        """Release resources."""
        ...


@runtime_checkable
class AsyncDisposable(Protocol):
    """Protocol for components that need async cleanup on container close."""

    async def aclose(self) -> None:
        """Release resources asynchronously."""
        ...
