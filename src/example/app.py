"""FastAPI application — the only file that imports the web framework.

The route handlers are thin: they receive a ``UserController`` via
dependency injection and delegate immediately. Business logic stays
in the controller, which has no idea it's running inside FastAPI.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from example.config import DbConfig
from example.controller import (  # noqa: TC001 — used in route annotations
    CreateUserRequest,
    UserController,
)
from example.domain import TenantId, User
from uncoiled import Container, EnvSource, bind_config
from uncoiled.fastapi import (
    Inject,
    RequestScopeMiddleware,
    RequestValueProvider,
    uncoiled_lifespan,
)

# ── Container setup ──────────────────────────────────────────────
#
# 1. Bind DbConfig from environment variables (e.g. DB_URL=...).
# 2. Register it as an instance so the container can inject it.
# 3. scan() discovers @component classes:
#      - SqliteUserRepository (provides=UserRepository, needs DbConfig)
#      - UserController (needs UserRepository + TenantId)
# 4. RequestScopeMiddleware extracts TenantId from each request
#    header and seeds it into the request scope. Components that
#    depend on TenantId receive it via normal constructor injection.

container = Container()
container.register_instance(bind_config(DbConfig, EnvSource()))
container.scan("example")

app = FastAPI(lifespan=uncoiled_lifespan(container))
app.add_middleware(
    RequestScopeMiddleware,  # ty: ignore[invalid-argument-type]
    container=container,
    request_values=[
        RequestValueProvider(
            TenantId,
            lambda r: TenantId(r.headers.get("x-tenant-id", "default")),
        ),
    ],
)

# ── Routes ───────────────────────────────────────────────────────


@app.get("/users")
def list_users(ctrl: Inject[UserController]) -> dict:
    """Return all users, scoped to the current tenant."""
    return {"tenant": ctrl.tenant, "users": ctrl.list_users()}


@app.get("/users/{user_id}")
def get_user(user_id: int, ctrl: Inject[UserController]) -> User:
    """Return a single user by ID."""
    try:
        return ctrl.get_user(user_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/users", status_code=201)
def create_user(body: CreateUserRequest, ctrl: Inject[UserController]) -> User:
    """Create a new user."""
    return ctrl.create_user(body)
