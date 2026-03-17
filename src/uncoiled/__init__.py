"""Dependency injection for modern Python."""

from importlib import metadata

from ._errors import DependencyResolutionError, FailureKind, ResolutionFailure
from ._qualifiers import Qualifier
from ._types import MISSING, AsyncDisposable, Disposable, Factory, Scope

__all__ = [
    "MISSING",
    "AsyncDisposable",
    "DependencyResolutionError",
    "Disposable",
    "Factory",
    "FailureKind",
    "Qualifier",
    "ResolutionFailure",
    "Scope",
]

__version__ = metadata.version(__name__)
