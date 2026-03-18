"""Tests for the example application.

Demonstrates two testing strategies:
1. Unit tests — construct the controller directly, no container
2. Integration tests — real app and routes, test double via container override
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from example.app import app, container
from example.controller import CreateUserRequest, UserController
from example.domain import User, UserRepository
from uncoiled.fastapi import configure_container

if TYPE_CHECKING:
    from collections.abc import Iterator


class InMemoryUserRepository:
    """Test double — swap in for SqliteUserRepository."""

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


# ── Pytest plugin fixtures ────────────────────────────────────────
#
# Override the default ``uncoiled_container`` to use the real app's
# container.  This enables the ``inject`` fixture and the
# ``uncoiled_override`` marker for tests that need them.


@pytest.fixture(scope="session")
def uncoiled_container() -> Iterator[None]:
    configure_container(app, container)
    container.start()
    yield container
    container.close()


# ── 1. Unit tests ────────────────────────────────────────────────


class TestUserControllerUnit:
    """Unit tests — no container, no HTTP, just plain Python."""

    def setup_method(self) -> None:
        self.ctrl = UserController(repo=InMemoryUserRepository())

    def test_list_users(self) -> None:
        users = self.ctrl.list_users()
        assert len(users) >= 1
        assert all(isinstance(u, User) for u in users)

    def test_get_existing_user(self) -> None:
        user = self.ctrl.get_user(1)
        assert user.id == 1
        assert user.name == "Alice"

    def test_get_missing_user_raises(self) -> None:
        with pytest.raises(LookupError, match="999"):
            self.ctrl.get_user(999)

    def test_create_user(self) -> None:
        user = self.ctrl.create_user(
            CreateUserRequest(name="Carol", email="carol@example.com"),
        )
        assert user.name == "Carol"
        assert user.id > 0
        assert self.ctrl.get_user(user.id) == user


# ── 2. Integration tests (HTTP against the real app) ─────────────


class TestFastAPIIntegration:
    """Hit the real app's routes with an in-memory repo swapped in.

    Uses ``uncoiled_override`` to replace both the repository and the
    controller (whose singleton was already cached with the original
    repo) so every test gets a fresh ``InMemoryUserRepository``.
    """

    @pytest.fixture(autouse=True)
    def _override(self) -> Iterator[None]:
        repo = InMemoryUserRepository()
        ctrl = UserController(repo=repo)
        with (
            container.override(UserRepository, repo),
            container.override(UserController, ctrl),
        ):
            yield

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
