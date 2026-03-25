"""``@config_properties`` decorator for binding config to frozen dataclasses."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, get_type_hints

from uncoiled._coercion import coerce

from ._relaxed import normalise

if TYPE_CHECKING:
    from ._sources import ConfigSource


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
            try:
                kwargs[field.name] = coerce(raw, hints[field.name])
            except (ValueError, TypeError) as exc:
                target = hints[field.name]
                type_name = getattr(target, "__name__", str(target))
                msg = f"Cannot coerce config key '{key}' value {raw!r} to {type_name}"
                raise ValueError(msg) from exc
        elif (
            field.default is not dataclasses.MISSING
            or field.default_factory is not dataclasses.MISSING
        ):
            pass  # Let the dataclass use its default
        else:
            msg = f"Missing required config value for '{key}'"
            raise ValueError(msg)

    return cls(**kwargs)
