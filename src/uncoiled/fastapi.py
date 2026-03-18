"""FastAPI integration — bridge the container into FastAPI's Depends() system."""

from __future__ import annotations

__all__ = [
    "Inject",
    "RequestScopeMiddleware",
    "configure_container",
    "inject_dependency",
    "uncoiled_lifespan",
]

import contextlib
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request

from ._container import Container  # noqa: TC001 — used at runtime in Depends()

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from starlette.types import ASGIApp, Receive, Scope, Send


def _get_container(request: Request) -> Container:
    """Extract the container from the app state."""
    container: Container = request.app.state.uncoiled_container
    return container


class Inject:
    """Shorthand for injecting a dependency from the container.

    Usage in route signatures::

        @app.get("/users")
        def list_users(ctrl: Inject[UserController]) -> list[User]: ...

    ``Inject[T]`` expands to ``Annotated[T, Depends(...)]`` so FastAPI
    resolves the type from the container automatically.
    """

    def __class_getitem__(cls, type_: type) -> type:
        """Return ``Annotated[T, Depends(...)]`` for the given type."""
        return Annotated[type_, inject_dependency(type_)]  # type: ignore[return-value]


def inject_dependency[T](type_: type[T]) -> T:
    """Create a FastAPI ``Depends`` that resolves *type_* from the container.

    Prefer ``Inject[T]`` in route signatures for brevity.
    """

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
            with self._container.request_context():
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
        app.state.uncoiled_container = container  # ty: ignore[unresolved-attribute]
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
    app.state.uncoiled_container = container  # ty: ignore[unresolved-attribute]
    container.start()
