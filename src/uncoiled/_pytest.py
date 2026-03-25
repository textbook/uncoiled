"""Pytest plugin for uncoiled — auto-discovered via entry point."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest

from ._container import Container

if TYPE_CHECKING:
    from collections.abc import Iterator


class Resolve:
    """Function-scoped helper to resolve types from the container."""

    def __init__(self, container: Container) -> None:
        self._container = container

    def __getitem__[T](self, key: type[T]) -> T:
        """Resolve a type from the container."""
        return self._container.get(key)


@pytest.fixture(scope="session")
def uncoiled_container() -> Iterator[Container]:
    """Session-scoped fixture providing a started container."""
    container = Container()
    container.start()
    yield container
    container.close()


@pytest.fixture
def inject(uncoiled_container: Container) -> Resolve:
    """Function-scoped fixture to resolve types from the container."""
    return Resolve(uncoiled_container)


@pytest.fixture(autouse=True)
def _uncoiled_overrides(
    request: pytest.FixtureRequest,
    uncoiled_container: Container,
) -> Iterator[None]:
    """Apply ``uncoiled_override`` markers as overrides for each test."""
    markers = list(request.node.iter_markers("uncoiled_override"))
    if not markers:
        yield
        return

    with contextlib.ExitStack() as stack:
        for marker in markers:
            type_ = marker.args[0]
            replacement = marker.args[1]
            qualifier = marker.kwargs.get("qualifier")
            stack.enter_context(
                uncoiled_container.override(type_, replacement, qualifier=qualifier),
            )
        yield


def pytest_configure(config: pytest.Config) -> None:
    """Register the ``uncoiled_override`` marker."""
    config.addinivalue_line(
        "markers",
        "uncoiled_override(type_, replacement, *, qualifier=None): "
        "override a container registration for the duration of the test",
    )
