"""Container class — the central dependency injection runtime."""

from __future__ import annotations

import contextlib
import importlib
import inspect
import pkgutil
from typing import TYPE_CHECKING, Self

from ._graph import ComponentNode, validate_graph
from ._inspection import DependencySpec, inspect_dependencies
from ._lifecycle import call_destroy, call_init
from ._scope import RequestScope, SingletonScope, TransientScope
from ._types import Scope

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import ModuleType

    from ._component import ComponentMetadata
    from ._scope import ScopeManager


class Container:
    """Central dependency injection container.

    Manage component registration, validation, lifecycle, and resolution.
    """

    def __init__(self) -> None:
        self._registrations: dict[tuple[type, str | None], ComponentNode] = {}
        self._scopes: dict[Scope, ScopeManager] = {
            Scope.SINGLETON: SingletonScope(),
            Scope.TRANSIENT: TransientScope(),
            Scope.REQUEST: RequestScope(),
        }
        self._instances: list[object] = []
        self._destroy_hooks: dict[type, str | None] = {}
        self._init_hooks: dict[type, str | None] = {}
        self._started = False

    def register(  # noqa: PLR0913
        self,
        cls: type,
        *,
        scope: Scope = Scope.SINGLETON,
        qualifier: str | None = None,
        provides: type | None = None,
        init_method: str | None = None,
        destroy_method: str | None = None,
    ) -> None:
        """Register a class as a component."""
        self._check_scope(scope)
        provides = provides or cls
        key = (provides, qualifier)
        self._registrations[key] = ComponentNode(
            impl=cls,
            provides=provides,
            qualifier=qualifier,
            scope=scope,
        )
        self._registrations[key].dependencies = inspect_dependencies(cls)
        if init_method:
            self._check_lifecycle_method(cls, init_method, "init_method")
            self._init_hooks[cls] = init_method
        if destroy_method:
            self._check_lifecycle_method(cls, destroy_method, "destroy_method")
            self._destroy_hooks[cls] = destroy_method

    def register_instance(
        self,
        instance: object,
        *,
        type_: type | None = None,
        qualifier: str | None = None,
        destroy_method: str | None = None,
    ) -> None:
        """Register a pre-constructed instance."""
        type_ = type_ or type(instance)
        key = (type_, qualifier)
        self._registrations[key] = ComponentNode(
            impl=type_,
            provides=type_,
            qualifier=qualifier,
        )
        self._scopes[Scope.SINGLETON].put(type_, instance, qualifier)
        self._instances.append(instance)
        if destroy_method:
            self._destroy_hooks[type_] = destroy_method

    def register_factory(  # noqa: PLR0913
        self,
        factory: object,
        *,
        return_type: type,
        scope: Scope = Scope.SINGLETON,
        qualifier: str | None = None,
        init_method: str | None = None,
        destroy_method: str | None = None,
    ) -> None:
        """Register a factory callable for a type."""
        self._check_scope(scope)
        key = (return_type, qualifier)
        node = ComponentNode(
            impl=return_type,
            provides=return_type,
            qualifier=qualifier,
            scope=scope,
            factory=factory,
        )
        node.dependencies = inspect_dependencies(factory)
        self._registrations[key] = node
        if init_method:
            self._init_hooks[return_type] = init_method
        if destroy_method:
            self._destroy_hooks[return_type] = destroy_method

    def scan(self, *modules: str | ModuleType) -> None:
        """Scan modules for ``@component``-decorated classes and register them."""
        for module in modules:
            if isinstance(module, str):
                module = importlib.import_module(module)  # noqa: PLW2901
            self._scan_module(module)

    def _scan_module(self, mod: ModuleType) -> None:
        """Scan a single module and its submodules for components."""
        self._register_from_module(mod)

        if hasattr(mod, "__path__"):
            for _importer, modname, _ispkg in pkgutil.walk_packages(
                mod.__path__,
                prefix=mod.__name__ + ".",
            ):
                submod = importlib.import_module(modname)
                self._register_from_module(submod)

    def _register_from_module(self, mod: ModuleType) -> None:
        """Register all ``@component``-decorated classes found in a module."""
        for _name, obj in inspect.getmembers(mod, inspect.isclass):
            meta: ComponentMetadata | None = getattr(obj, "__uncoiled__", None)
            if meta is not None:
                self.register(obj, scope=meta.scope, qualifier=meta.qualifier)

    def validate(self) -> None:
        """Validate the dependency graph eagerly."""
        validate_graph(self._registrations)

    def start(self) -> None:
        """Validate the graph and instantiate all singletons."""
        self.validate()
        singleton = self._scopes[Scope.SINGLETON]
        for key, node in self._registrations.items():
            if (
                node.scope is Scope.SINGLETON
                and singleton.get(node.provides, key[1]) is None
            ):
                self._resolve(node.provides, key[1])
        self._started = True

    def close(self) -> None:
        """Destroy instances in reverse creation order."""
        errors: list[Exception] = []
        for instance in reversed(self._instances):
            try:
                destroy_method = self._destroy_hooks.get(type(instance))
                call_destroy(instance, destroy_method)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
        self._instances.clear()
        for scope_manager in self._scopes.values():
            scope_manager.clear()
        self._started = False
        if errors:
            msg = "errors during container close"
            raise ExceptionGroup(msg, errors)

    def get[T](self, type_: type[T], qualifier: str | None = None) -> T:
        """Resolve a single instance of the given type."""
        return self._resolve(type_, qualifier)

    def get_all[T](self, type_: type[T], qualifier: str | None = None) -> list[T]:
        """Resolve all registered implementations of the given type."""
        results: list[T] = []
        for (reg_type, qual), node in self._registrations.items():
            if qualifier is not None and qual != qualifier:
                continue
            if reg_type is type_ or (
                isinstance(reg_type, type) and issubclass(reg_type, type_)
            ):
                results.append(self._resolve(node.provides, qual))  # type: ignore[arg-type]
        return results

    def _resolve[T](self, type_: type[T], qualifier: str | None = None) -> T:
        """Resolve a type from the container."""
        key = (type_, qualifier)
        node = self._registrations.get(key)
        if node is None:
            msg = f"No component registered for type {type_.__name__}"
            if qualifier:
                msg += f" with qualifier '{qualifier}'"
            raise LookupError(msg)

        scope_manager = self._scopes.get(node.scope)
        if scope_manager:
            cached = scope_manager.get(type_, qualifier)
            if cached is not None:
                return cached

        instance = self._create_instance(node)

        if scope_manager:
            scope_manager.put(type_, instance, qualifier)

        if node.scope is not Scope.TRANSIENT or node.impl in self._destroy_hooks:
            self._instances.append(instance)
        call_init(instance, self._init_hooks.get(node.impl))

        return instance  # type: ignore[return-value]

    def _create_instance(self, node: ComponentNode) -> object:
        """Create an instance from a ComponentNode."""
        kwargs: dict[str, object] = {}
        for dep in node.dependencies:
            self._resolve_dependency(dep, kwargs)

        if node.factory is not None:
            return node.factory(**kwargs)  # type: ignore[operator]

        return node.impl(**kwargs)

    def _resolve_dependency(
        self,
        dep: DependencySpec,
        kwargs: dict[str, object],
    ) -> None:
        """Resolve a single dependency into kwargs."""
        if dep.is_list:
            kwargs[dep.name] = self.get_all(dep.required_type, dep.qualifier)
        elif dep.optional or dep.has_default:
            dep_key = (dep.required_type, dep.qualifier)
            if dep_key in self._registrations:
                kwargs[dep.name] = self._resolve(
                    dep.required_type,
                    dep.qualifier,
                )
            elif dep.optional and not dep.has_default:
                kwargs[dep.name] = None
        else:
            kwargs[dep.name] = self._resolve(dep.required_type, dep.qualifier)

    @contextlib.contextmanager
    def override(
        self,
        type_: type,
        replacement: object,
        *,
        qualifier: str | None = None,
    ) -> Iterator[None]:
        """Temporarily replace a registration.

        *replacement* may be a class (re-registered) or an instance.
        """
        key = (type_, qualifier)
        old_node = self._registrations.get(key)
        singleton = self._scopes[Scope.SINGLETON]
        old_cached = singleton.get(type_, qualifier)

        # Remove existing cache entry so the override takes effect
        singleton.remove(type_, qualifier)

        # Install the replacement
        if isinstance(replacement, type):
            self.register(replacement, provides=type_, qualifier=qualifier)
        else:
            self.register_instance(replacement, type_=type_, qualifier=qualifier)

        try:
            yield
        finally:
            # Remove the override's cache entry
            singleton.remove(type_, qualifier)

            # Restore original registration (or remove if there was none)
            if old_node is None:
                self._registrations.pop(key, None)
            else:
                self._registrations[key] = old_node

            # Restore original cached instance
            if old_cached is not None:
                singleton.put(type_, old_cached, qualifier)

    def request_context(self) -> contextlib.AbstractContextManager[None]:
        """Enter a new request scope context."""
        scope = self._scopes[Scope.REQUEST]
        return scope.context()  # type: ignore[union-attr]

    def fork(self) -> Container:
        """Create a child container with shared registrations."""
        child = Container()
        child._registrations = dict(self._registrations)
        child._init_hooks = dict(self._init_hooks)
        child._destroy_hooks = dict(self._destroy_hooks)
        return child

    @staticmethod
    def _check_lifecycle_method(target: type, method_name: str, kind: str) -> None:
        """Raise if the named method does not exist on the class."""
        if not hasattr(target, method_name):
            msg = f"{kind} '{method_name}' does not exist on {target.__name__}"
            raise ValueError(msg)

    def _check_scope(self, scope: Scope) -> None:
        """Raise if the scope has no registered manager."""
        if scope not in self._scopes:
            msg = f"No scope manager registered for {scope.value!r}"
            raise ValueError(msg)

    def __enter__(self) -> Self:
        """Start the container as a context manager."""
        self.start()
        return self

    def __exit__(self, *_args: object) -> None:
        """Close the container."""
        self.close()
