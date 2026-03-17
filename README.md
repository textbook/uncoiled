# Uncoiled

Dependency injection for modern Python.

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
- `uv run pytest` to run the tests

  [uv]: https://docs.astral.sh/uv/
