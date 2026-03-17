"""Configuration sources with layered precedence."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol, runtime_checkable

from ._relaxed import normalise

_MIN_QUOTED_LEN = 2


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
            with Path(path).open() as f:
                for raw_line in f:
                    stripped = raw_line.strip()
                    if not stripped or stripped.startswith("#") or "=" not in stripped:
                        continue
                    key, _, value = stripped.partition("=")
                    key = key.strip()
                    value = value.strip()
                    if (
                        len(value) >= _MIN_QUOTED_LEN
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


class YamlSource:
    """Configuration source backed by a YAML file (requires ``pyyaml``)."""

    def __init__(self, path: str) -> None:
        self._data: dict[str, str] = {}
        self._load(path)

    def _load(self, path: str) -> None:
        """Parse a YAML file and flatten into dotted keys."""
        try:
            import yaml  # noqa: PLC0415
        except ModuleNotFoundError:
            msg = "pyyaml is required for YamlSource — install uncoiled[yaml]"
            raise ImportError(msg) from None

        try:
            with Path(path).open() as f:
                raw = yaml.safe_load(f)
        except FileNotFoundError:
            return

        if isinstance(raw, dict):
            self._flatten(raw, "")

    def _flatten(self, obj: dict[str, object], prefix: str) -> None:
        """Recursively flatten nested dicts into dotted-key strings."""
        for key, value in obj.items():
            full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
            if isinstance(value, dict):
                self._flatten(value, full_key)  # ty: ignore[invalid-argument-type]
            else:
                self._data[normalise(full_key)] = str(value)

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
