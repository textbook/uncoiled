"""Integration tests for the example application.

Uses the real ``app`` and its routes.  A module-scoped
``uncoiled_container`` wires ``InMemoryUserRepository`` directly so
``UserController`` is resolved with the test double — no override
hack needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from example.app import app
from example.controller import UserController
from example.domain import User, UserRepository
from uncoiled import Container, Inject
from uncoiled.fastapi import configure_container

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


@pytest.fixture(scope="module")
def uncoiled_container() -> Iterator[Container]:
    c = Container()
    c.scan("example")
    c.register(InMemoryUserRepository, provides=UserRepository)
    configure_container(app, c)
    with c:
        yield c


class TestViaInject:
    """Resolve through the ``inject`` fixture — no HTTP."""

    def test_controller_uses_in_memory_repo(self, inject: Inject) -> None:
        ctrl = inject[UserController]
        assert isinstance(ctrl.repo, InMemoryUserRepository)

    def test_get_seeded_user(self, inject: Inject) -> None:
        ctrl = inject[UserController]
        assert ctrl.get_user(1).name == "Alice"


class TestHTTPRoutes:
    """Hit the real app routes via ASGI transport."""

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        )

    @pytest.mark.anyio
    async def test_list_users(self) -> None:
        async with self._client() as client:
            resp = await client.get("/users")
        assert resp.status_code == 200
        users = resp.json()
        assert len(users) >= 1
        assert users[0]["name"] == "Alice"

    @pytest.mark.anyio
    async def test_get_user(self) -> None:
        async with self._client() as client:
            resp = await client.get("/users/1")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Alice"

    @pytest.mark.anyio
    async def test_get_missing_user_returns_404(self) -> None:
        async with self._client() as client:
            resp = await client.get("/users/999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_user(self) -> None:
        async with self._client() as client:
            resp = await client.post(
                "/users",
                json={"name": "Carol", "email": "carol@example.com"},
            )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Carol"
