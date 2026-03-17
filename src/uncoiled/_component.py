"""``@component`` decorator for marking DI-managed classes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import overload

from ._types import Scope


@dataclass(frozen=True)
class ComponentMetadata:
    """Metadata attached to a class by the ``@component`` decorator."""

    scope: Scope = Scope.SINGLETON
    qualifier: str | None = None


@overload
def component(cls: type, /) -> type: ...


@overload
def component(
    *,
    scope: Scope = ...,
    qualifier: str | None = ...,
) -> _ComponentDecorator: ...


def component(
    cls: type | None = None,
    /,
    *,
    scope: Scope = Scope.SINGLETON,
    qualifier: str | None = None,
) -> type | _ComponentDecorator:
    """Mark a class as a DI-managed component.

    Can be used with or without arguments::

        @component
        class UserService: ...

        @component(scope=Scope.TRANSIENT, qualifier="special")
        class SpecialService: ...

    Attaches ``ComponentMetadata`` as a ``__uncoiled__`` attribute.
    Does not modify class behaviour.
    """
    meta = ComponentMetadata(scope=scope, qualifier=qualifier)

    if cls is not None:
        cls.__uncoiled__ = meta  # ty: ignore[unresolved-attribute]
        return cls

    return _ComponentDecorator(meta)


class _ComponentDecorator:
    """Callable returned by ``@component(...)`` with arguments."""

    def __init__(self, meta: ComponentMetadata) -> None:
        self._meta = meta

    def __call__(self, cls: type) -> type:
        cls.__uncoiled__ = self._meta  # ty: ignore[unresolved-attribute]
        return cls
