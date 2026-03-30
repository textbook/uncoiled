"""Init/destroy hook management for component lifecycle."""

from __future__ import annotations

import logging

from ._types import AsyncDisposable, Disposable

_log = logging.getLogger("uncoiled")


def call_init(instance: object, init_method: str | None = None) -> None:
    """Call the init hook on an instance if applicable."""
    if init_method is not None:
        _log.debug("Calling %s.%s()", type(instance).__name__, init_method)
        method = getattr(instance, init_method)
        method()


async def async_call_init(
    instance: object,
    init_method: str | None = None,
) -> None:
    """Call the init hook on an instance, supporting async methods."""
    if init_method is not None:
        _log.debug("Calling %s.%s() (async)", type(instance).__name__, init_method)
        method = getattr(instance, init_method)
        result = method()
        if hasattr(result, "__await__"):
            await result


def call_destroy(instance: object, destroy_method: str | None = None) -> None:
    """Call the destroy hook on an instance if applicable.

    Checks explicit destroy_method first, then Disposable protocol.
    """
    if destroy_method is not None:
        _log.debug("Calling %s.%s()", type(instance).__name__, destroy_method)
        method = getattr(instance, destroy_method)
        method()
    elif isinstance(instance, Disposable):
        _log.debug("Calling %s.close()", type(instance).__name__)
        instance.close()


async def async_call_destroy(
    instance: object,
    destroy_method: str | None = None,
) -> None:
    """Call the destroy hook on an instance, supporting async methods.

    Check explicit destroy_method first, then AsyncDisposable, then Disposable.
    """
    if destroy_method is not None:
        _log.debug("Calling %s.%s() (async)", type(instance).__name__, destroy_method)
        method = getattr(instance, destroy_method)
        result = method()
        if hasattr(result, "__await__"):
            await result
    elif isinstance(instance, AsyncDisposable):
        _log.debug("Calling %s.aclose()", type(instance).__name__)
        await instance.aclose()
    elif isinstance(instance, Disposable):
        _log.debug("Calling %s.close()", type(instance).__name__)
        instance.close()
