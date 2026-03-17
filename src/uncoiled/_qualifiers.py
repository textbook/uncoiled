"""Qualifier annotation for disambiguating components of the same type."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Qualifier:
    """Marker for use with ``typing.Annotated`` to qualify a dependency.

    Example::

        def __init__(self, repo: Annotated[Repository, Qualifier("postgres")]):
            ...

    """

    name: str
