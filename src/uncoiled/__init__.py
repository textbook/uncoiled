"""Dependency injection for modern Python."""

from importlib import metadata

from ._errors import DependencyResolutionError, FailureKind, ResolutionFailure

__all__ = [
    "DependencyResolutionError",
    "FailureKind",
    "ResolutionFailure",
]

__version__ = metadata.version(__name__)
