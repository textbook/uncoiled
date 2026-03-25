"""HTTP routes — thin layer that delegates to injected controllers."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from example.controller import (  # noqa: TC001 — used in route annotations
    CreateUserRequest,
    UserController,
)
from example.domain import User  # noqa: TC001 — used in route annotations
from uncoiled.fastapi import Inject  # noqa: TC001 — used at runtime by FastAPI

user_router = APIRouter(prefix="/users")


@user_router.get("")
def list_users(controller: Inject[UserController]) -> dict:
    """Return all users, scoped to the current tenant."""
    return {"tenant": controller.tenant, "users": controller.list_users()}


@user_router.get("/{user_id}")
def get_user(user_id: int, controller: Inject[UserController]) -> User:
    """Return a single user by ID."""
    try:
        return controller.get_user(user_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@user_router.post("", status_code=201)
def create_user(
    body: CreateUserRequest,
    controller: Inject[UserController],
) -> User:
    """Create a new user."""
    return controller.create_user(body)
