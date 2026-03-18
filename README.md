# Uncoiled

Dependency injection for modern Python.

## Quick Start

Define your domain as plain Python — protocols for ports, classes for logic:

```python
# domain.py — no framework imports
class UserRepository(Protocol):
    def find_by_id(self, user_id: int) -> User | None: ...

# controller.py — depends on the protocol, not a concrete class
@component
class UserController:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

    def get_user(self, user_id: int) -> User: ...

# infra.py — @component(provides=...) registers against the protocol
@component(provides=UserRepository)
class InMemoryUserRepository: ...
```

The container discovers `@component` classes automatically via `scan()`:

```python
# app.py
container = Container()
container.scan("myapp")

app = FastAPI(lifespan=uncoiled_lifespan(container))

@app.get("/users/{user_id}")
def get_user(user_id: int, ctrl: Inject[UserController]) -> User:
    return ctrl.get_user(user_id)
```

The container inspects `UserController.__init__`, sees it needs a
`UserRepository`, and auto-wires `InMemoryUserRepository`. No `@inject`,
no `Provide[T]`, no service locator calls. Swap the repository for a
database-backed implementation and the controller doesn't change.

The full dependency graph is validated at startup — missing dependencies
and cycles are caught immediately with actionable error messages, not at
first request.

See [`src/example/`](src/example/) for a complete runnable app with tests.

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
