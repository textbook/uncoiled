"""Tests for the example application.

Demonstrates two testing strategies:
1. Unit tests — construct the controller with an in-memory repo, no container
2. Integration tests — swap SqliteUserRepository for InMemoryUserRepository
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from example.config import DbConfig
from example.controller import CreateUserRequest, UserController
from example.domain import User, UserRepository
from example.infra import SqliteUserRepository
from uncoiled import Container, DictSource, bind_config
from uncoiled.fastapi import Inject, configure_container, uncoiled_lifespan


def _make_container() -> Container:
    """Build a fresh container with the example app's registrations."""
    c = Container()
    c.register_instance(bind_config(DbConfig, DictSource({})))
    c.scan("example")
    return c


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


class TestContainerWiring:
    """Verify the container wires the right implementations."""

    def test_scan_discovers_sqlite_repo(self) -> None:
        c = _make_container()
        c.start()
        ctrl = c.get(UserController)
        assert isinstance(ctrl.repo, SqliteUserRepository)

    def test_swap_to_in_memory_for_tests(self) -> None:
        """Register the test double directly — no database needed."""
        c = Container()
        c.register(InMemoryUserRepository, provides=UserRepository)
        c.register(UserController)
        c.start()
        ctrl = c.get(UserController)
        assert isinstance(ctrl.repo, InMemoryUserRepository)
        assert ctrl.get_user(1).name == "Alice"


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
        def create_user(body: CreateUserRequest, ctrl: Inject[UserController]) -> User:
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
