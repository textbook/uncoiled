"""Environment variable injection marker."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnvVar:
    """Marker for injecting an environment variable via ``Annotated``.

    Usage::

        class MyService:
            def __init__(
                self,
                db_url: Annotated[str, EnvVar("DATABASE_URL")] = ":memory:",
            ) -> None: ...

    The container resolves ``EnvVar("DATABASE_URL")`` from ``os.environ``
    at injection time, falling back to the parameter default if the
    variable is unset.
    """

    name: str
