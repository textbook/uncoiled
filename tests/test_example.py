"""Tests for the example application.

Demonstrates three testing strategies:
1. Unit tests — construct the controller with an in-memory repo, no container
2. Container tests — use the ``inject`` fixture and ``uncoiled_override`` marker
3. Integration tests — full HTTP stack with in-memory repo via container override
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest
from fastapi import FastAPI

from example.config import DbConfig
from example.controller import CreateUserRequest, UserController
from example.domain import User, UserRepository
from example.infra import SqliteUserRepository
from uncoiled import Container, DictSource, bind_config
from uncoiled import Inject as PytestInject
from uncoiled.fastapi import Inject, configure_container, uncoiled_lifespan

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
# Override the session-scoped ``uncoiled_container`` fixture so the
# ``inject`` fixture and ``uncoiled_override`` marker work with the
# example app's registrations.


@pytest.fixture(scope="session")
def uncoiled_container() -> Iterator[Container]:
    c = Container()
    c.register_instance(bind_config(DbConfig, DictSource({})))
    c.scan("example")
    c.start()
    yield c
    c.close()


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


# ── 2. Container tests (pytest plugin) ───────────────────────────


class TestContainerWiring:
    """Use the ``inject`` fixture to resolve types from the container."""

    def test_scan_discovers_sqlite_repo(self, inject: PytestInject) -> None:
        ctrl = inject[UserController]
        assert isinstance(ctrl.repo, SqliteUserRepository)

    @pytest.mark.uncoiled_override(UserRepository, InMemoryUserRepository)
    def test_override_swaps_repo(self, inject: PytestInject) -> None:
        repo = inject[UserRepository]
        assert isinstance(repo, InMemoryUserRepository)
        user = repo.find_by_id(1)
        assert user is not None
        assert user.name == "Alice"


# ── 3. Integration tests (HTTP) ──────────────────────────────────


class TestFastAPIIntegration:
    """Integration tests — in-memory repo, real HTTP stack."""

    @pytest.fixture(autouse=True)
    def _app(self) -> None:
        """Build a fresh app + container with in-memory repo for each test."""
        self.container = Container()
        self.container.register_instance(bind_config(DbConfig, DictSource({})))
        self.container.register(InMemoryUserRepository, provides=UserRepository)
        self.container.register(UserController)
        self.app = FastAPI(lifespan=uncoiled_lifespan(self.container))

        # Re-declare routes on the fresh app
        @self.app.get("/users")
        def list_users(ctrl: Inject[UserController]) -> list[User]:
            return ctrl.list_users()

        @self.app.get("/users/{user_id}")
        def get_user(user_id: int, ctrl: Inject[UserController]) -> User:
            try:
                return ctrl.get_user(user_id)
            except LookupError as exc:
                from fastapi import HTTPException  # noqa: PLC0415

                raise HTTPException(status_code=404, detail=str(exc)) from exc

        @self.app.post("/users", status_code=201)
        def create_user(
            body: CreateUserRequest,
            ctrl: Inject[UserController],
        ) -> User:
            return ctrl.create_user(body)

        configure_container(self.app, self.container)

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
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
