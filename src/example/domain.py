"""Domain layer — pure business logic with no framework imports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class TenantId(str):
    """Identifies the current tenant — injected from the request."""

    __slots__ = ()


@dataclass(frozen=True)
class User:
    """A user in the system."""

    id: int
    name: str
    email: str


class UserRepository(Protocol):
    """Port for user persistence — implemented by the infrastructure layer."""

    def find_by_id(self, user_id: int) -> User | None: ...

    def list_all(self) -> list[User]: ...

    def save(self, user: User) -> User: ...
