"""``@config_properties`` decorator for binding config to frozen dataclasses."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import TYPE_CHECKING, get_type_hints

from ._relaxed import normalise

if TYPE_CHECKING:
    from ._sources import ConfigSource


def _parse_bool(value: str) -> bool:
    """Parse a string to a boolean value."""
    if value.lower() in ("true", "1", "yes", "on"):
        return True
    if value.lower() in ("false", "0", "no", "off"):
        return False
    msg = f"Cannot coerce '{value}' to bool"
    raise ValueError(msg)


_COERCIONS: dict[type, object] = {
    str: str,
    int: int,
    float: float,
    bool: _parse_bool,
    Path: Path,
}


def _coerce(value: str, target_type: type) -> object:
    """Coerce a string value to the target type."""
    if target_type is list or (
        hasattr(target_type, "__origin__") and target_type.__origin__ is list
    ):
        return [item.strip() for item in value.split(",") if item.strip()]

    coercer = _COERCIONS.get(target_type)
    if coercer is not None:
        return coercer(value)  # ty: ignore[call-non-callable]

    return value


def config_properties(
    prefix: str,
) -> _ConfigPropertiesDecorator:
    """Decorate a dataclass to bind configuration values by prefix.

    Example::

        @config_properties("db")
        @dataclass(frozen=True)
        class DbConfig:
            host: str = "localhost"
            port: int = 5432

    """
    return _ConfigPropertiesDecorator(prefix)


class _ConfigPropertiesDecorator:
    """Return value of ``config_properties(prefix)``."""

    def __init__(self, prefix: str) -> None:
        self._prefix = prefix

    def __call__(self, cls: type) -> type:
        """Attach prefix metadata to the class."""
        cls.__config_prefix__ = self._prefix  # ty: ignore[unresolved-attribute]
        return cls


def bind_config[T](cls: type[T], source: ConfigSource) -> T:
    """Create an instance of a config dataclass by reading values from a source."""
    prefix = getattr(cls, "__config_prefix__", "")
    hints = get_type_hints(cls)
    fields = dataclasses.fields(cls)
    kwargs: dict[str, object] = {}

    for field in fields:
        key = f"{prefix}.{field.name}" if prefix else field.name
        raw = source.get(normalise(key))
        if raw is not None:
            kwargs[field.name] = _coerce(raw, hints[field.name])
        elif (
            field.default is not dataclasses.MISSING
            or field.default_factory is not dataclasses.MISSING
        ):
            pass  # Let the dataclass use its default
        else:
            msg = f"Missing required config value for '{key}'"
            raise ValueError(msg)

    return cls(**kwargs)
