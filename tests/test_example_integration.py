"""Integration tests for the example application.

Uses ``create_app`` from the production module so the tests exercise
the exact same routes and middleware as the real app — only the
container registrations differ (``InMemoryUserRepository`` instead
of ``SqliteUserRepository``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import httpx
import pytest

from example.app import REQUEST_VALUES, create_app
from example.controller import UserController
from example.domain import TenantId, User, UserRepository
from uncoiled import Container, Resolve
from uncoiled.fastapi import configure_container

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi import FastAPI


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


@pytest.fixture(scope="module")
def _test_app() -> FastAPI:
    """Build the app once per module so the container fixture can wire it."""
    c = Container()
    c.scan("example")
    c.register(InMemoryUserRepository, provides=UserRepository)
    application = create_app(c)
    configure_container(
        application,
        c,
        request_values=REQUEST_VALUES,
    )
    return application


@pytest.fixture(scope="module")
def uncoiled_container(_test_app: FastAPI) -> Iterator[Container]:
    c: Container = _test_app.state.uncoiled_container
    with c:
        yield c


class TestViaInject:
    """Resolve through the ``inject`` fixture — no HTTP."""

    def test_controller_uses_in_memory_repo(
        self,
        inject: Resolve,
        uncoiled_container: Container,
    ) -> None:
        with uncoiled_container.request_context():
            uncoiled_container.provide_request_value(
                TenantId,
                TenantId("test"),
            )
            controller = inject[UserController]
            assert isinstance(controller.repo, InMemoryUserRepository)

    def test_get_seeded_user(
        self,
        inject: Resolve,
        uncoiled_container: Container,
    ) -> None:
        with uncoiled_container.request_context():
            uncoiled_container.provide_request_value(
                TenantId,
                TenantId("test"),
            )
            controller = inject[UserController]
            assert controller.get_user(1).name == "Alice"


class TestHTTPRoutes:
    """Hit the real app routes via ASGI transport."""

    _headers: ClassVar[dict[str, str]] = {"x-tenant-id": "acme"}

    @pytest.fixture(autouse=True)
    def _app(self, _test_app: FastAPI) -> None:
        self._test_app = _test_app

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self._test_app),
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
