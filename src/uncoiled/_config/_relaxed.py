"""Relaxed binding name normalisation for configuration keys.

Normalises different naming conventions to a canonical dotted form:

- ``MY_DB_HOST`` → ``my.db.host``
- ``my-db-host`` → ``my.db.host``
- ``my.db.host`` → ``my.db.host``
"""

from __future__ import annotations

import re

_SEPARATOR_RE = re.compile(r"[-_.]")


def normalise(key: str) -> str:
    """Normalise a configuration key to canonical dotted lowercase form."""
    return _SEPARATOR_RE.sub(".", key).lower()
