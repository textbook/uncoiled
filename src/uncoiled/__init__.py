"""Dependency injection for modern Python."""

from importlib import metadata

from ._component import ComponentMetadata, component
from ._config._binding import bind_config, config_properties
from ._config._profiles import get_active_profiles
from ._config._relaxed import normalise
from ._config._sources import (
    ConfigSource,
    DictSource,
    DotEnvSource,
    EnvSource,
    LayeredSource,
)
from ._container import Container
from ._errors import DependencyResolutionError, FailureKind, ResolutionFailure
from ._graph import ComponentNode, build_graph, validate_graph
from ._inspection import DependencySpec, inspect_dependencies
from ._lifecycle import async_call_destroy, async_call_init, call_destroy, call_init
from ._pytest import Inject
from ._qualifiers import Qualifier
from ._scope import RequestScope, ScopeManager, SingletonScope, TransientScope
from ._types import MISSING, AsyncDisposable, Disposable, Factory, Scope

__all__ = [
    "MISSING",
    "AsyncDisposable",
    "ComponentMetadata",
    "ComponentNode",
    "ConfigSource",
    "Container",
    "DependencyResolutionError",
    "DependencySpec",
    "DictSource",
    "Disposable",
    "DotEnvSource",
    "EnvSource",
    "Factory",
    "FailureKind",
    "Inject",
    "LayeredSource",
    "Qualifier",
    "RequestScope",
    "ResolutionFailure",
    "Scope",
    "ScopeManager",
    "SingletonScope",
    "TransientScope",
    "async_call_destroy",
    "async_call_init",
    "bind_config",
    "build_graph",
    "call_destroy",
    "call_init",
    "component",
    "config_properties",
    "get_active_profiles",
    "inspect_dependencies",
    "normalise",
    "validate_graph",
]

__version__ = metadata.version(__name__)
