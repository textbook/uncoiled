"""Application controller — orchestrates use cases.

Depends on the ``UserRepository`` protocol, not a concrete implementation.
The DI container wires in the real thing at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass

from example.domain import User, UserRepository
from uncoiled import component


@dataclass(frozen=True)
class CreateUserRequest:
    """Payload for creating a user."""

    name: str
    email: str


@component
@dataclass
class UserController:
    """Thin orchestration layer between HTTP and domain logic.

    This class has *zero* web-framework imports — it doesn't know about
    FastAPI, Flask, or any other web framework. It only depends on
    ``UserRepository``, which is a plain Protocol.
    """

    repo: UserRepository

    def get_user(self, user_id: int) -> User:
        """Retrieve a single user or raise."""
        user = self.repo.find_by_id(user_id)
        if user is None:
            msg = f"User {user_id} not found"
            raise LookupError(msg)
        return user

    def list_users(self) -> list[User]:
        """Return all users."""
        return self.repo.list_all()

    def create_user(self, request: CreateUserRequest) -> User:
        """Create and return a new user."""
        user = User(id=0, name=request.name, email=request.email)
        return self.repo.save(user)
