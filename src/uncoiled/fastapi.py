"""FastAPI integration — bridge the container into FastAPI's Depends() system."""

from __future__ import annotations

__all__ = [
    "Inject",
    "RequestScopeMiddleware",
    "RequestValueProvider",
    "configure_container",
    "inject_dependency",
    "uncoiled_lifespan",
]

import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request

from ._container import Container  # noqa: TC001 — used at runtime in Depends()

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Sequence

    from fastapi import FastAPI
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


@dataclass(frozen=True)
class RequestValueProvider:
    """Declare a value extracted from each HTTP request and injected into the container.

    *type_* is the type to register; *extractor* receives the Starlette
    ``Request`` and returns the value; *qualifier* disambiguates when
    multiple values share the same type.
    """

    type_: type
    extractor: Callable[[Request], object]
    qualifier: str | None = None


class RequestScopeMiddleware:
    """ASGI middleware that opens a request scope context per request."""

    def __init__(
        self,
        app: ASGIApp,
        container: Container,
        request_values: Sequence[RequestValueProvider] = (),
    ) -> None:
        """Initialise with the ASGI app and container."""
        self._app = app
        self._container = container
        self._request_values = request_values
        for rv in request_values:
            container.register_request_value(rv.type_, qualifier=rv.qualifier)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Wrap HTTP and WebSocket requests in a request scope context."""
        if scope["type"] in {"http", "websocket"}:
            with self._container.request_context():
                if self._request_values and scope["type"] == "http":
                    request = Request(scope, receive, send)
                    for rv in self._request_values:
                        self._container.provide_request_value(
                            rv.type_,
                            rv.extractor(request),
                            qualifier=rv.qualifier,
                        )
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
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        existing: Container | None = getattr(
            app.state,
            "uncoiled_container",
            None,
        )
        if existing is not None:
            yield
            return
        app.state.uncoiled_container = container
        container.start()
        try:
            yield
        finally:
            container.close()

    return _lifespan


def configure_container(
    app: FastAPI,
    container: Container,
    request_values: Sequence[RequestValueProvider] = (),
) -> None:
    """Attach a container to the app and start it.

    Convenience for test setups where the ASGI lifespan is not triggered.
    Pass *request_values* so the container registers them before
    ``start()`` validates the dependency graph.
    """
    for rv in request_values:
        container.register_request_value(rv.type_, qualifier=rv.qualifier)
    app.state.uncoiled_container = container
    container.start()
