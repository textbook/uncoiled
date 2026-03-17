"""FastAPI integration — bridge the container into FastAPI's Depends() system."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request

from ._container import Container
from ._scope import RequestScope
from ._types import Scope as UncoiledScope

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from starlette.types import ASGIApp, Receive, Scope, Send


def _get_container(request: Request) -> Container:
    """Extract the container from the app state."""
    container: Container = request.app.state.uncoiled_container
    return container


class _InjectMarker:
    """Marker for ``Annotated[T, Inject]`` in FastAPI route signatures."""


Inject = _InjectMarker()
"""Use as ``Annotated[MyService, Inject]`` in route parameters."""


def inject_dependency[T](type_: type[T]) -> T:
    """Create a FastAPI ``Depends`` that resolves *type_* from the container."""

    def _resolve(
        container: Annotated[Container, Depends(_get_container)],
    ) -> T:
        return container.get(type_)

    return Depends(_resolve)


class RequestScopeMiddleware:
    """ASGI middleware that opens a request scope context per request."""

    def __init__(self, app: ASGIApp, container: Container) -> None:
        """Initialise with the ASGI app and container."""
        self._app = app
        self._container = container

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Wrap HTTP requests in a request scope context."""
        if scope["type"] in {"http", "websocket"}:
            request_scope: RequestScope = self._container._scopes[  # noqa: SLF001
                UncoiledScope.REQUEST
            ]  # type: ignore[assignment]
            with request_scope.context():
                await self._app(scope, receive, send)
        else:
            await self._app(scope, receive, send)


def uncoiled_lifespan(
    container: Container,
) -> Callable[..., contextlib.AbstractAsyncContextManager[None]]:
    """Create a lifespan factory for ``FastAPI(lifespan=...)``.

    Sets ``app.state.uncoiled_container`` so route dependencies can
    resolve types from the container.
    """

    @contextlib.asynccontextmanager
    async def _lifespan(app: object) -> AsyncIterator[None]:
        app.state.uncoiled_container = container  # type: ignore[union-attr]
        container.start()
        try:
            yield
        finally:
            container.close()

    return _lifespan


def configure_container(app: object, container: Container) -> None:
    """Attach a container to the app and start it.

    Convenience for test setups where the ASGI lifespan is not triggered.
    """
    app.state.uncoiled_container = container  # type: ignore[union-attr]
    container.start()
