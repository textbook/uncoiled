"""Unit tests for the example application.

Construct the controller directly with a test double — no container,
no HTTP, just plain Python.
"""

from __future__ import annotations

import pytest

from example.controller import CreateUserRequest, UserController
from example.domain import User

from .example_helpers import InMemoryUserRepository


class TestUserController:
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
