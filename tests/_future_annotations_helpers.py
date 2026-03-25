"""Helper module using ``from __future__ import annotations`` for testing.

All type annotations in this module are stringified at runtime due to
PEP 563 deferred evaluation. This exercises inspect.get_annotations(eval_str=True).
"""

from __future__ import annotations

from dataclasses import dataclass


class Repository:
    pass


class UserService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo


class OptionalService:
    def __init__(self, repo: Repository | None = None) -> None:
        self.repo = repo


class ForwardRefService:
    def __init__(self, late: LateDefinedClass) -> None:
        self.late = late


class LateDefinedClass:
    pass


@dataclass
class ParentConfig:
    host: str = "localhost"
    port: int = 5432


@dataclass
class ChildConfig(ParentConfig):
    name: str = "mydb"
