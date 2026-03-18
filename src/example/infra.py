"""Infrastructure layer — concrete implementations of domain ports."""

from __future__ import annotations

import sqlite3

from example.config import DbConfig  # noqa: TC001 — injected at runtime
from example.domain import User, UserRepository
from uncoiled import Scope, component


@component(provides=UserRepository, scope=Scope.SINGLETON)
class SqliteUserRepository:
    """SQLite-backed implementation of ``UserRepository``.

    Receives ``DbConfig`` via constructor injection — the container
    auto-wires it from the registered config instance.
    """

    def __init__(self, config: DbConfig) -> None:
        self._conn = sqlite3.connect(config.url, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS users "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT)",
        )
        self._conn.commit()

    def find_by_id(self, user_id: int) -> User | None:
        """Look up a user by ID."""
        row = self._conn.execute(
            "SELECT id, name, email FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return User(id=row[0], name=row[1], email=row[2])

    def list_all(self) -> list[User]:
        """Return all users."""
        rows = self._conn.execute("SELECT id, name, email FROM users").fetchall()
        return [User(id=r[0], name=r[1], email=r[2]) for r in rows]

    def save(self, user: User) -> User:
        """Insert a user and return it with the generated ID."""
        cursor = self._conn.execute(
            "INSERT INTO users (name, email) VALUES (?, ?)",
            (user.name, user.email),
        )
        self._conn.commit()
        return User(id=cursor.lastrowid, name=user.name, email=user.email)  # ty: ignore[invalid-argument-type]
