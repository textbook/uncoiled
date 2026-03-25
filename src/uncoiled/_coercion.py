"""Shared type coercion for string values (env vars and config properties)."""

from __future__ import annotations

from pathlib import Path

_BOOL_TRUE = frozenset({"1", "on", "true", "yes"})
_BOOL_FALSE = frozenset({"0", "false", "no", "off"})


def _parse_bool(value: str) -> bool:
    """Parse a string to a boolean value."""
    lower = value.lower()
    if lower in _BOOL_TRUE:
        return True
    if lower in _BOOL_FALSE:
        return False
    msg = f"Cannot coerce {value!r} to bool"
    raise ValueError(msg)


_COERCIONS: dict[type, object] = {
    str: str,
    int: int,
    float: float,
    bool: _parse_bool,
    Path: Path,
}


def coerce(value: str, target: type) -> object:
    """Coerce a string *value* to *target* type.

    Supported targets: ``str``, ``int``, ``float``, ``bool``, ``Path``,
    and ``list`` / ``list[str]`` (comma-separated).

    Raises
    ------
    ValueError
        If the conversion fails (e.g. non-numeric string to ``int``).

    """
    if target is list or (hasattr(target, "__origin__") and target.__origin__ is list):
        return [item.strip() for item in value.split(",") if item.strip()]

    coercer = _COERCIONS.get(target)
    if coercer is not None:
        return coercer(value)  # ty: ignore[call-non-callable]

    msg = f"Unsupported coercion target type: {target}"
    raise ValueError(msg)
