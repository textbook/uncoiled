# Uncoiled

Dependency injection for modern Python.

## Quick Start

Define your services as plain classes — no framework imports or markers needed:

```python
# services.py
from dataclasses import dataclass


class UserRepository:
    def find(self, user_id: int) -> dict:
        return {"id": user_id, "name": "Alice"}


class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

    def get_user(self, user_id: int) -> dict:
        return self.repo.find(user_id)


@dataclass(frozen=True)
class AppConfig:
    version: str = "0.1.0"
```

Wire them up with a container and serve via FastAPI:

```python
# app.py
from typing import Annotated

from fastapi import FastAPI

from uncoiled import Container
from uncoiled.fastapi import inject_dependency, uncoiled_lifespan

from services import AppConfig, UserRepository, UserService

container = Container()
container.register(UserRepository)
container.register(UserService)
container.register_instance(AppConfig(version="1.0.0"))

app = FastAPI(lifespan=uncoiled_lifespan(container))


@app.get("/users/{user_id}")
def get_user(
    user_id: int,
    service: Annotated[UserService, inject_dependency(UserService)],
) -> dict:
    return service.get_user(user_id)
```

Uncoiled auto-wires `UserService` from its `__init__` signature — no `@inject`,
no `Provide[T]`, no service locator calls. The container validates the full
dependency graph at startup and gives actionable error messages if anything is
missing.

## Development

- Install [uv]
- Clone this repository
- In the repo root, run `uv sync` to download Python (if required), create a virtual environment, and install dependencies
- Run `uv run pre-commit install` to set up the pre-commit hooks

### Preflight

When a task is finished, run:

- `uv run ty check` to check the types
- `uv run ruff check` to run the linting
- `uv run ruff format --check` to check the formatting
- `uv run coverage run --module pytest` to run the tests

  [uv]: https://docs.astral.sh/uv/
