"""Dependency injection for modern Python."""

from importlib import metadata

from ._component import ComponentMetadata, component
from ._errors import DependencyResolutionError, FailureKind, ResolutionFailure
from ._graph import ComponentNode, build_graph, validate_graph
from ._inspection import DependencySpec, inspect_dependencies
from ._qualifiers import Qualifier
from ._types import MISSING, AsyncDisposable, Disposable, Factory, Scope

__all__ = [
    "MISSING",
    "AsyncDisposable",
    "ComponentMetadata",
    "ComponentNode",
    "DependencyResolutionError",
    "DependencySpec",
    "Disposable",
    "Factory",
    "FailureKind",
    "Qualifier",
    "ResolutionFailure",
    "Scope",
    "build_graph",
    "component",
    "inspect_dependencies",
    "validate_graph",
]

__version__ = metadata.version(__name__)
