"""Unit tests for the example application.

Construct the controller directly with a mock — no container,
no HTTP, just plain Python.
"""

from __future__ import annotations

import logging
from unittest.mock import Mock

import pytest

from example.controller import CreateUserRequest, UserController
from example.domain import TenantId, User, UserRepository


class TestUserController:
    def setup_method(self) -> None:
        self.repo = Mock(spec_set=UserRepository)
        self.controller = UserController(
            repo=self.repo,
            tenant=TenantId("test-tenant"),
            logger=logging.getLogger("test"),
        )

    def test_get_user(self) -> None:
        alice = User(id=1, name="Alice", email="alice@example.com")
        self.repo.find_by_id.return_value = alice

        assert self.controller.get_user(1) == alice
        self.repo.find_by_id.assert_called_once_with(1)

    def test_get_missing_user_raises(self) -> None:
        self.repo.find_by_id.return_value = None

        with pytest.raises(LookupError, match="999"):
            self.controller.get_user(999)

    def test_list_users(self) -> None:
        users = [User(id=1, name="Alice", email="alice@example.com")]
        self.repo.list_all.return_value = users

        assert self.controller.list_users() == users

    def test_create_user(self) -> None:
        saved = User(id=42, name="Carol", email="carol@example.com")
        self.repo.save.return_value = saved

        result = self.controller.create_user(
            CreateUserRequest(name="Carol", email="carol@example.com"),
        )
        assert result == saved
        self.repo.save.assert_called_once()
