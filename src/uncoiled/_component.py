"""``@component`` and ``@factory`` decorators for marking DI-managed types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, overload

from ._types import Scope

if TYPE_CHECKING:
    from collections.abc import Callable

    type _FactoryTarget = Callable[..., object] | classmethod


@dataclass(frozen=True)
class ComponentMetadata:
    """Metadata attached to a class or factory by a DI decorator."""

    scope: Scope = Scope.SINGLETON
    qualifier: str | None = None
    provides: type | None = None


def _attach(target: object, meta: ComponentMetadata) -> object:
    """Attach metadata to any decorator target (class, function, or classmethod)."""
    if isinstance(target, classmethod):
        target.__func__.__uncoiled__ = meta  # type: ignore[attr-defined]
    else:
        target.__uncoiled__ = meta  # type: ignore[attr-defined]
    return target


class _Decorator:
    """Callable returned by ``@component(...)`` or ``@factory(...)`` with arguments."""

    def __init__(self, meta: ComponentMetadata) -> None:
        self._meta = meta

    def __call__(self, target: object) -> object:
        return _attach(target, self._meta)


# region @component — marks a class for constructor injection


@overload
def component(cls: type, /) -> type: ...


@overload
def component(
    *,
    scope: Scope = ...,
    qualifier: str | None = ...,
    provides: type | None = ...,
) -> _Decorator: ...


def component(
    cls: type | None = None,
    /,
    *,
    scope: Scope = Scope.SINGLETON,
    qualifier: str | None = None,
    provides: type | None = None,
) -> type | _Decorator:
    """Mark a class as a DI-managed component.

    Can be used with or without arguments::

        @component
        class UserService: ...

        @component(scope=Scope.TRANSIENT, qualifier="special")
        class SpecialService: ...

        @component(provides=Repository)
        class PostgresRepository: ...

    Attaches ``ComponentMetadata`` as a ``__uncoiled__`` attribute.
    Does not modify class behaviour.
    """
    meta = ComponentMetadata(scope=scope, qualifier=qualifier, provides=provides)

    if cls is not None:
        _attach(cls, meta)
        return cls

    return _Decorator(meta)


# endregion

# region @factory — marks a function or classmethod as a DI-managed factory


@overload
def factory(target: _FactoryTarget, /) -> _FactoryTarget: ...


@overload
def factory(
    *,
    scope: Scope = ...,
    qualifier: str | None = ...,
    provides: type | None = ...,
) -> _Decorator: ...


def factory(
    target: _FactoryTarget | None = None,
    /,
    *,
    scope: Scope = Scope.SINGLETON,
    qualifier: str | None = None,
    provides: type | None = None,
) -> _FactoryTarget | _Decorator:
    """Mark a function or classmethod as a DI-managed factory.

    Can be used with or without arguments::

        @factory
        def create_client(config: Config) -> HttpClient: ...

        @factory(scope=Scope.TRANSIENT, qualifier="special")
        def create_service() -> Service: ...

        @factory
        @classmethod
        def from_config(cls, source: ConfigSource) -> Repository: ...

    The return type annotation determines the provided type.  Use
    ``provides=`` to override when the interface differs from the
    concrete return type.

    Attaches ``ComponentMetadata`` as a ``__uncoiled__`` attribute.
    Does not modify callable behaviour.
    """
    meta = ComponentMetadata(scope=scope, qualifier=qualifier, provides=provides)

    if target is not None:
        _attach(target, meta)
        return target

    return _Decorator(meta)


# endregion
