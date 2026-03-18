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


# ── Production wiring ────────────────────────────────────────────
#
# 1. Bind DbConfig from environment variables (e.g. DB_URL=...).
# 2. scan() discovers @component classes in the example package.
# 3. create_app() adds RequestScopeMiddleware (extracts TenantId
#    from X-Tenant-Id header) and includes the user routes.

container = Container()
container.register_instance(bind_config(DbConfig, EnvSource()))
container.scan("example")

app = create_app(container)
