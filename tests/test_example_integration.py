"""Integration tests for the example application.

Builds a test ``FastAPI`` app that mirrors the production app's routes
but uses an ``InMemoryUserRepository``.  A module-scoped container
wires everything, including ``RequestValueProvider`` for the tenant
header — exactly as the production app does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from example.controller import CreateUserRequest, UserController
from example.domain import TenantId, User, UserRepository
from uncoiled import Container, Inject
from uncoiled.fastapi import Inject as WebInject
from uncoiled.fastapi import (
    RequestScopeMiddleware,
    RequestValueProvider,
    configure_container,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


class InMemoryUserRepository:
    """In-memory stand-in for SqliteUserRepository."""

    def __init__(self) -> None:
        self._users: dict[int, User] = {
            1: User(id=1, name="Alice", email="alice@example.com"),
            2: User(id=2, name="Bob", email="bob@example.com"),
        }
        self._next_id = 3

    def find_by_id(self, user_id: int) -> User | None:
        return self._users.get(user_id)

    def list_all(self) -> list[User]:
        return list(self._users.values())

    def save(self, user: User) -> User:
        saved = User(id=self._next_id, name=user.name, email=user.email)
        self._users[saved.id] = saved
        self._next_id += 1
        return saved


_REQUEST_VALUES = [
    RequestValueProvider(
        TenantId,
        lambda r: TenantId(r.headers.get("x-tenant-id", "test")),
    ),
]

_test_app = FastAPI()


def _build_routes(test_app: FastAPI) -> None:
    @test_app.get("/users")
    def list_users(ctrl: WebInject[UserController]) -> dict:
        return {"tenant": ctrl.tenant, "users": ctrl.list_users()}

    @test_app.get("/users/{user_id}")
    def get_user(
        user_id: int,
        ctrl: WebInject[UserController],
    ) -> User:
        try:
            return ctrl.get_user(user_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @test_app.post("/users", status_code=201)
    def create_user(
        body: CreateUserRequest,
        ctrl: WebInject[UserController],
    ) -> User:
        return ctrl.create_user(body)


_build_routes(_test_app)


@pytest.fixture(scope="module")
def uncoiled_container() -> Iterator[Container]:
    c = Container()
    c.scan("example")
    c.register(InMemoryUserRepository, provides=UserRepository)
    _test_app.add_middleware(
        RequestScopeMiddleware,  # ty: ignore[invalid-argument-type]
        container=c,
        request_values=_REQUEST_VALUES,
    )
    configure_container(
        _test_app,
        c,
        request_values=_REQUEST_VALUES,
    )
    with c:
        yield c


class TestViaInject:
    """Resolve through the ``inject`` fixture — no HTTP."""

    def test_controller_uses_in_memory_repo(
        self,
        inject: Inject,
        uncoiled_container: Container,
    ) -> None:
        with uncoiled_container.request_context():
            uncoiled_container.provide_request_value(
                TenantId,
                TenantId("test"),
            )
            ctrl = inject[UserController]
            assert isinstance(ctrl.repo, InMemoryUserRepository)

    def test_get_seeded_user(
        self,
        inject: Inject,
        uncoiled_container: Container,
    ) -> None:
        with uncoiled_container.request_context():
            uncoiled_container.provide_request_value(
                TenantId,
                TenantId("test"),
            )
            ctrl = inject[UserController]
            assert ctrl.get_user(1).name == "Alice"


class TestHTTPRoutes:
    """Hit the test app routes via ASGI transport."""

    _headers: ClassVar[dict[str, str]] = {"x-tenant-id": "acme"}

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_test_app),
            base_url="http://test",
        )

    @pytest.mark.anyio
    async def test_list_users(self) -> None:
        async with self._client() as client:
            resp = await client.get("/users", headers=self._headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["tenant"] == "acme"
        assert len(body["users"]) >= 1
        assert body["users"][0]["name"] == "Alice"

    @pytest.mark.anyio
    async def test_get_user(self) -> None:
        async with self._client() as client:
            resp = await client.get("/users/1", headers=self._headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Alice"

    @pytest.mark.anyio
    async def test_get_missing_user_returns_404(self) -> None:
        async with self._client() as client:
            resp = await client.get("/users/999", headers=self._headers)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_user(self) -> None:
        async with self._client() as client:
            resp = await client.post(
                "/users",
                json={"name": "Carol", "email": "carol@example.com"},
                headers=self._headers,
            )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Carol"
