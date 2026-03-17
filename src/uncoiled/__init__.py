"""Dependency injection for modern Python."""

from importlib import metadata

from ._errors import DependencyResolutionError, FailureKind, ResolutionFailure
from ._inspection import DependencySpec, inspect_dependencies
from ._qualifiers import Qualifier
from ._types import MISSING, AsyncDisposable, Disposable, Factory, Scope

__all__ = [
    "MISSING",
    "AsyncDisposable",
    "DependencyResolutionError",
    "DependencySpec",
    "Disposable",
    "Factory",
    "FailureKind",
    "Qualifier",
    "ResolutionFailure",
    "Scope",
    "inspect_dependencies",
]

__version__ = metadata.version(__name__)
