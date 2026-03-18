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
from example.domain import UserRepository
from uncoiled import Container, Inject
from uncoiled.fastapi import configure_container

from .example_helpers import InMemoryUserRepository

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(scope="module")
def uncoiled_container() -> Iterator[Container]:
    c = Container()
    c.register(InMemoryUserRepository, provides=UserRepository)
    c.register(UserController)
    configure_container(app, c)
    c.start()
    yield c
    c.close()


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
