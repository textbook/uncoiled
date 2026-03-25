"""FastAPI application — assembles container, middleware, and routes.

This is the composition root: it wires everything together but
contains no business logic or route definitions.
"""

from __future__ import annotations

from fastapi import FastAPI

from example.config import DbConfig
from example.domain import TenantId
from example.routes import user_router
from uncoiled import Container, EnvSource, bind_config
from uncoiled.fastapi import (
    RequestScopeMiddleware,
    RequestValueProvider,
    uncoiled_lifespan,
)

REQUEST_VALUES = [
    RequestValueProvider(
        TenantId,
        lambda r: TenantId(r.headers.get("x-tenant-id", "default")),
    ),
]


def create_app(container: Container) -> FastAPI:
    """Build the FastAPI application.

    Accepts a container so tests can supply their own registrations
    while exercising the exact same routes and middleware.
    """
    application = FastAPI(lifespan=uncoiled_lifespan(container))
    application.add_middleware(
        RequestScopeMiddleware,  # ty: ignore[invalid-argument-type]
        container=container,
        request_values=REQUEST_VALUES,
    )
    application.include_router(user_router)
    return application


def create_default_app() -> FastAPI:
    """Build the production app with env-sourced config.

    Container creation happens inside this function so that
    importing the module does not trigger side effects (env var
    reads, component scanning).  ASGI servers call this via::

        uvicorn example.app:app --factory
    """
    c = Container()
    c.register_instance(bind_config(DbConfig, EnvSource()))
    c.scan("example")
    return create_app(c)
