# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Uncoiled is a dependency injection framework for modern Python (>=3.12). Uses uv for project management.

## Commands

```bash
uv run coverage run --module pytest                    # run all tests with coverage
uv run coverage run --module pytest tests/test_foo.py  # run a single test file
uv run coverage run --module pytest -k test_name       # run a single test by name
uv run coverage report                                 # show coverage report
uv run ty check                  # type check
uv run ruff check                # lint (ALL rules enabled)
uv run ruff check --fix          # lint with auto-fix
uv run ruff format --check       # check formatting
uv run ruff format               # auto-format
```

Run all checks before finishing a task: `uv run ty check && uv run ruff check && uv run ruff format --check && uv run coverage run --module pytest`

## Code Layout

- `src/uncoiled/` — package source (flat module structure, private modules prefixed with `_`)
- `src/uncoiled/__init__.py` — public API; all public types/functions must be re-exported here
- `tests/` — pytest tests; must import from `uncoiled`, never from private modules like `uncoiled._errors`
- CI runs checks across Python 3.12, 3.13, and 3.14

## Linting

Ruff is configured with **all rules enabled** (`select = ["ALL"]`). Notable ignores:
- `COM812` (trailing commas) — handled by formatter
- `D105`, `D203`, `D213` — docstring style preferences
- Tests ignore all docstring rules (`D`) and assert warnings (`S101`)

## Workflow

Tasks are tracked as GitHub issues. Work on a branch, open a PR with `Closes #N`, and merge when CI is green. Docs live in the GitHub wiki.
