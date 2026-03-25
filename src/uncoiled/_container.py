"""Container class — the central dependency injection runtime."""

from __future__ import annotations

import contextlib
import importlib
import inspect
import logging
import os
import pkgutil
from typing import TYPE_CHECKING, Self

from ._coercion import coerce
from ._graph import ComponentNode, validate_graph
from ._inspection import DependencySpec, inspect_dependencies
from ._lifecycle import async_call_destroy, async_call_init, call_destroy, call_init
from ._scope import RequestScope, SingletonScope, TransientScope
from ._types import Scope

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import ModuleType

    from ._component import ComponentMetadata
    from ._scope import ScopeManager


_REQUEST_VALUE_SENTINEL = object()


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
        self._instances: list[tuple[object, type, str | None]] = []
        self._generators: list[object] = []
        self._destroy_hooks: dict[tuple[type, str | None], str | None] = {}
        self._init_hooks: dict[tuple[type, str | None], str | None] = {}
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
        replace: bool = False,
    ) -> None:
        """Register a class as a component."""
        self._check_scope(scope)
        provides = provides or cls
        self._check_provides(cls, provides)
        key = (provides, qualifier)
        self._check_duplicate(key, replace=replace)
        self._registrations[key] = ComponentNode(
            impl=cls,
            provides=provides,
            qualifier=qualifier,
            scope=scope,
        )
        self._registrations[key].dependencies = inspect_dependencies(cls)
        if init_method:
            self._check_lifecycle_method(cls, init_method, "init_method")
            self._init_hooks[(cls, qualifier)] = init_method
        if destroy_method:
            self._check_lifecycle_method(cls, destroy_method, "destroy_method")
            self._destroy_hooks[(cls, qualifier)] = destroy_method

    def register_instance(
        self,
        instance: object,
        *,
        type_: type | None = None,
        qualifier: str | None = None,
        destroy_method: str | None = None,
        replace: bool = False,
    ) -> None:
        """Register a pre-constructed instance."""
        type_ = type_ or type(instance)
        key = (type_, qualifier)
        self._check_duplicate(key, replace=replace)
        self._registrations[key] = ComponentNode(
            impl=type_,
            provides=type_,
            qualifier=qualifier,
        )
        self._scopes[Scope.SINGLETON].put(type_, instance, qualifier)
        self._instances.append((instance, type_, qualifier))
        if destroy_method:
            self._destroy_hooks[(type_, qualifier)] = destroy_method

    def register_factory(  # noqa: PLR0913
        self,
        factory: object,
        *,
        return_type: type,
        scope: Scope = Scope.SINGLETON,
        qualifier: str | None = None,
        init_method: str | None = None,
        destroy_method: str | None = None,
        replace: bool = False,
    ) -> None:
        """Register a factory callable for a type."""
        self._check_scope(scope)
        key = (return_type, qualifier)
        self._check_duplicate(key, replace=replace)
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
            self._init_hooks[(return_type, qualifier)] = init_method
        if destroy_method:
            self._destroy_hooks[(return_type, qualifier)] = destroy_method

    def register_request_value(
        self,
        type_: type,
        *,
        qualifier: str | None = None,
    ) -> None:
        """Declare that a type will be provided per-request.

        This creates a registration entry so graph validation succeeds,
        but the actual value must be seeded via ``provide_request_value``
        inside each request context.
        """
        key = (type_, qualifier)
        node = ComponentNode(
            impl=type_,
            provides=type_,
            qualifier=qualifier,
            scope=Scope.REQUEST,
            factory=_REQUEST_VALUE_SENTINEL,
        )
        self._registrations[key] = node

    def provide_request_value(
        self,
        type_: type,
        value: object,
        *,
        qualifier: str | None = None,
    ) -> None:
        """Seed a value into the current request scope."""
        key = (type_, qualifier)
        node = self._registrations.get(key)
        if node is None or node.factory is not _REQUEST_VALUE_SENTINEL:
            msg = f"No request value registered for type {type_.__name__}"
            if qualifier:
                msg += f" with qualifier '{qualifier}'"
            raise LookupError(msg)
        self._scopes[Scope.REQUEST].put(type_, value, qualifier)

    def scan(self, *modules: str | ModuleType) -> None:
        """Scan modules for ``@component``-decorated classes and register them."""
        for module in modules:
            mod = importlib.import_module(module) if isinstance(module, str) else module
            self._scan_module(mod)

    def _scan_module(self, mod: ModuleType) -> None:
        """Scan a single module and its submodules for components."""
        seen: set[type] = set()
        self._register_from_module(mod, seen)

        if hasattr(mod, "__path__"):
            for _importer, modname, _ispkg in pkgutil.walk_packages(
                mod.__path__,
                prefix=mod.__name__ + ".",
            ):
                submod = importlib.import_module(modname)
                self._register_from_module(submod, seen)

    def _register_from_module(
        self,
        mod: ModuleType,
        seen: set[type],
    ) -> None:
        """Register all ``@component``-decorated classes found in a module."""
        for _name, obj in inspect.getmembers(mod, inspect.isclass):
            if obj in seen:
                continue
            meta: ComponentMetadata | None = getattr(obj, "__uncoiled__", None)
            if meta is not None:
                seen.add(obj)
                self.register(
                    obj,
                    scope=meta.scope,
                    qualifier=meta.qualifier,
                    provides=meta.provides,
                )

    def validate(self) -> None:
        """Validate the dependency graph eagerly."""
        validate_graph(self._registrations)

    def visualise(self) -> str:
        """Render the dependency graph as a Mermaid flowchart.

        Returns a string that can be embedded in Markdown::

            ```mermaid
            print(container.visualise())
            ```
        """
        from ._visualise import render_mermaid  # noqa: PLC0415

        return render_mermaid(self._registrations)

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

    async def astart(self) -> None:
        """Validate the graph and instantiate all singletons (async)."""
        self.validate()
        singleton = self._scopes[Scope.SINGLETON]
        for key, node in self._registrations.items():
            if (
                node.scope is Scope.SINGLETON
                and singleton.get(node.provides, key[1]) is None
            ):
                await self._aresolve(node.provides, key[1])
        self._started = True

    def close(self) -> None:
        """Destroy instances in reverse creation order."""
        errors: list[Exception] = []
        for instance, impl, qualifier in reversed(self._instances):
            try:
                destroy_method = self._destroy_hooks.get((impl, qualifier))
                call_destroy(instance, destroy_method)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
        self._exhaust_generators(errors)
        self._instances.clear()
        self._generators.clear()
        for scope_manager in self._scopes.values():
            scope_manager.clear()
        self._started = False
        if errors:
            msg = "errors during container close"
            raise ExceptionGroup(msg, errors)

    async def aclose(self) -> None:
        """Destroy instances in reverse creation order (async)."""
        errors: list[Exception] = []
        for instance, impl, qualifier in reversed(self._instances):
            try:
                destroy_method = self._destroy_hooks.get((impl, qualifier))
                await async_call_destroy(instance, destroy_method)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
        await self._aexhaust_generators(errors)
        self._instances.clear()
        self._generators.clear()
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
                results.append(self._resolve(node.provides, qual))  # ty: ignore[invalid-argument-type]
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

        hook_key = (node.impl, qualifier)
        if node.scope is not Scope.TRANSIENT or hook_key in self._destroy_hooks:
            self._instances.append((instance, node.impl, qualifier))
        call_init(instance, self._init_hooks.get(hook_key))

        return instance  # ty: ignore[invalid-return-type]

    async def _aresolve[T](self, type_: type[T], qualifier: str | None = None) -> T:
        """Resolve a type from the container (async)."""
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

        instance = await self._acreate_instance(node)

        if scope_manager:
            scope_manager.put(type_, instance, qualifier)

        hook_key = (node.impl, qualifier)
        if node.scope is not Scope.TRANSIENT or hook_key in self._destroy_hooks:
            self._instances.append((instance, node.impl, qualifier))
        await async_call_init(instance, self._init_hooks.get(hook_key))

        return instance  # ty: ignore[invalid-return-type]

    def _create_instance(self, node: ComponentNode) -> object:
        """Create an instance from a ComponentNode."""
        if node.factory is _REQUEST_VALUE_SENTINEL:
            msg = (
                f"Request value for {node.provides.__name__} was not provided "
                f"in the current request context"
            )
            raise LookupError(msg)

        kwargs: dict[str, object] = {}
        for dep in node.dependencies:
            self._resolve_dependency(dep, kwargs, node=node)

        if node.factory is not None:
            result = node.factory(**kwargs)  # ty: ignore[call-non-callable]
            if inspect.isgenerator(result):
                instance = next(result)
                self._generators.append(result)
                return instance
            if inspect.isasyncgen(result):
                msg = (
                    "Async generator factories are not supported in "
                    "synchronous resolution — use astart() and aclose()"
                )
                raise TypeError(msg)
            return result

        return node.impl(**kwargs)

    async def _acreate_instance(self, node: ComponentNode) -> object:
        """Create an instance from a ComponentNode (async)."""
        if node.factory is _REQUEST_VALUE_SENTINEL:
            msg = (
                f"Request value for {node.provides.__name__} was not provided "
                f"in the current request context"
            )
            raise LookupError(msg)

        kwargs: dict[str, object] = {}
        for dep in node.dependencies:
            self._resolve_dependency(dep, kwargs, node=node)

        if node.factory is not None:
            result = node.factory(**kwargs)  # ty: ignore[call-non-callable]
            if inspect.isasyncgen(result):
                instance = await result.__anext__()
                self._generators.append(result)
                return instance
            if inspect.isgenerator(result):
                instance = next(result)
                self._generators.append(result)
                return instance
            return result

        return node.impl(**kwargs)

    def _resolve_dependency(
        self,
        dep: DependencySpec,
        kwargs: dict[str, object],
        *,
        node: ComponentNode,
    ) -> None:
        """Resolve a single dependency into kwargs."""
        if dep.env_var is not None:
            value = os.environ.get(dep.env_var)
            if value is not None:
                kwargs[dep.name] = coerce(value, dep.required_type)
            elif not dep.has_default:
                msg = (
                    f"Environment variable {dep.env_var!r} is not set"
                    " and no default was provided"
                )
                raise LookupError(msg)
        elif (
            dep.required_type is logging.Logger
            and (dep.required_type, dep.qualifier) not in self._registrations
        ):
            kwargs[dep.name] = logging.getLogger(node.impl.__module__)
        elif dep.is_list:
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
            self.register(
                replacement,
                provides=type_,
                qualifier=qualifier,
                replace=True,
            )
        else:
            self.register_instance(
                replacement,
                type_=type_,
                qualifier=qualifier,
                replace=True,
            )

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
        return scope.context()  # ty: ignore[unresolved-attribute]

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

    def _check_duplicate(
        self,
        key: tuple[type, str | None],
        *,
        replace: bool,
    ) -> None:
        """Raise if a registration already exists and replace is not set."""
        if not replace and key in self._registrations:
            type_, qualifier = key
            msg = f"A registration for {type_.__name__} already exists"
            if qualifier:
                msg += f" with qualifier '{qualifier}'"
            msg += "; pass replace=True to override"
            raise ValueError(msg)

    @staticmethod
    def _check_provides(impl: type, provides: type) -> None:
        """Raise if *impl* is not a subclass of *provides*."""
        if provides is impl:
            return
        try:
            is_sub = issubclass(impl, provides)
        except TypeError:
            return
        if not is_sub:
            msg = f"{impl.__name__} is not a subclass of {provides.__name__}"
            raise TypeError(msg)

    def _exhaust_generators(self, errors: list[Exception]) -> None:
        """Advance sync generators past yield to run cleanup code."""
        for gen in reversed(self._generators):
            try:
                with contextlib.suppress(StopIteration):
                    next(gen)  # ty: ignore[invalid-argument-type]
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

    async def _aexhaust_generators(self, errors: list[Exception]) -> None:
        """Advance all generators (sync and async) past yield."""
        for gen in reversed(self._generators):
            try:
                if inspect.isasyncgen(gen):
                    with contextlib.suppress(StopAsyncIteration):
                        await gen.__anext__()
                else:
                    with contextlib.suppress(StopIteration):
                        next(gen)  # ty: ignore[invalid-argument-type]
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

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

    async def __aenter__(self) -> Self:
        """Start the container as an async context manager."""
        await self.astart()
        return self

    async def __aexit__(self, *_args: object) -> None:
        """Close the container asynchronously."""
        await self.aclose()
