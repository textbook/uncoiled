"""Profile resolution via the ``UNCOILED_PROFILES`` environment variable."""

from __future__ import annotations

import os

PROFILES_ENV_VAR = "UNCOILED_PROFILES"


def get_active_profiles() -> list[str]:
    """Return the list of active profiles from the environment.

    Read from ``UNCOILED_PROFILES`` env var (comma-separated).
    """
    raw = os.environ.get(PROFILES_ENV_VAR, "")
    if not raw.strip():
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]
