"""Configuration sources with layered precedence."""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from ._relaxed import normalise


@runtime_checkable
class ConfigSource(Protocol):
    """Protocol for configuration value sources."""

    def get(self, key: str) -> str | None:
        """Return the value for the given key, or None if not found."""
        ...


class DictSource:
    """Configuration source backed by a plain dictionary."""

    def __init__(self, data: dict[str, str]) -> None:
        self._data = {normalise(k): v for k, v in data.items()}

    def get(self, key: str) -> str | None:
        """Return the value for the normalised key."""
        return self._data.get(normalise(key))


class EnvSource:
    """Configuration source that reads from environment variables."""

    def get(self, key: str) -> str | None:
        """Return the env var value, trying the original key then uppercase."""
        value = os.environ.get(key)
        if value is not None:
            return value
        return os.environ.get(key.upper().replace(".", "_"))


class DotEnvSource:
    """Configuration source that parses a ``.env`` file."""

    def __init__(self, path: str = ".env") -> None:
        self._data: dict[str, str] = {}
        self._load(path)

    def _load(self, path: str) -> None:
        """Parse a .env file into the data dict."""
        try:
            with open(path) as f:  # noqa: PTH123
                for line in f:
                    line = line.strip()  # noqa: PLW2901
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()
                    if (
                        len(value) >= 2  # noqa: PLR2004
                        and value[0] == value[-1]
                        and value[0] in ('"', "'")
                    ):
                        value = value[1:-1]
                    self._data[normalise(key)] = value
        except FileNotFoundError:
            pass

    def get(self, key: str) -> str | None:
        """Return the value for the normalised key."""
        return self._data.get(normalise(key))


class LayeredSource:
    """Combine multiple sources with priority (first match wins)."""

    def __init__(self, *sources: ConfigSource) -> None:
        self._sources = sources

    def get(self, key: str) -> str | None:
        """Return the first non-None value from the source chain."""
        for source in self._sources:
            value = source.get(key)
            if value is not None:
                return value
        return None
