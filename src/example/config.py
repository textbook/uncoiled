"""Configuration — bound from environment variables at startup."""

from __future__ import annotations

from dataclasses import dataclass

from uncoiled import config_properties


@config_properties("db")
@dataclass(frozen=True)
class DbConfig:
    """Database connection settings."""

    url: str = ":memory:"
