"""Shared test doubles for the example application."""

from __future__ import annotations

from example.domain import User


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
