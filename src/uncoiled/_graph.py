"""Dependency graph builder with cycle detection and validation."""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ._errors import DependencyResolutionError, FailureKind, ResolutionFailure
from ._inspection import DependencySpec, inspect_dependencies
from ._types import Scope

_log = logging.getLogger("uncoiled")

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class ComponentNode:
    """A node in the dependency graph representing a registered component."""

    impl: type
    provides: type
    qualifier: str | None = None
    dependencies: list[DependencySpec] = field(default_factory=list)
    scope: Scope = Scope.SINGLETON
    factory: Callable[..., object] | None = None


def _collect_auto_deps(
    registrations: dict[tuple[type, str | None], ComponentNode],
    auto_keys: set[tuple[type, str | None]],
) -> dict[tuple[type, str | None], list[tuple[type, str | None]]]:
    """Pre-compute registered dependency keys for each AUTO node."""
    auto_deps: dict[tuple[type, str | None], list[tuple[type, str | None]]] = {}
    for key in auto_keys:
        node = registrations[key]
        if not node.dependencies:
            target = node.factory if node.factory is not None else node.impl
            node.dependencies = inspect_dependencies(target)
        auto_deps[key] = [
            (dep.required_type, dep.qualifier)
            for dep in node.dependencies
            if not dep.is_list
            and dep.env_var is None
            and (dep.required_type, dep.qualifier) in registrations
        ]
    return auto_deps


def _infer_scope(
    dep_keys: list[tuple[type, str | None]],
    registrations: dict[tuple[type, str | None], ComponentNode],
    resolved: set[tuple[type, str | None]],
) -> tuple[Scope, bool]:
    """Infer the scope for an AUTO node from its dependencies.

    Returns (inferred_scope, has_unresolved_auto_deps).
    """
    has_unresolved = False
    for dk in dep_keys:
        dep_scope = registrations[dk].scope
        if dep_scope is Scope.AUTO and dk not in resolved:
            has_unresolved = True
        elif dep_scope is Scope.REQUEST:
            return Scope.REQUEST, False
    return Scope.SINGLETON, has_unresolved


def _resolve_auto_scopes(
    registrations: dict[tuple[type, str | None], ComponentNode],
) -> list[ResolutionFailure]:
    """Resolve AUTO-scoped components to concrete scopes via fixed-point iteration."""
    auto_keys = {key for key, node in registrations.items() if node.scope is Scope.AUTO}
    if not auto_keys:
        return []

    auto_deps = _collect_auto_deps(registrations, auto_keys)

    resolved: set[tuple[type, str | None]] = set()
    changed = True
    while changed:
        changed = False
        for key in auto_keys - resolved:
            inferred, has_unresolved = _infer_scope(
                auto_deps[key],
                registrations,
                resolved,
            )
            if inferred is Scope.REQUEST or not has_unresolved:
                registrations[key].scope = inferred
                resolved.add(key)
                changed = True
                _log.debug(
                    "AUTO scope resolved: %s -> %s",
                    registrations[key].impl.__name__,
                    inferred.value,
                )

    # Any remaining AUTO nodes form a cycle among themselves.
    unresolved = auto_keys - resolved
    if not unresolved:
        return []
    for key in unresolved:
        registrations[key].scope = Scope.SINGLETON
    names = sorted(registrations[k].impl.__name__ for k in unresolved)
    return [
        ResolutionFailure(
            kind=FailureKind.AUTO_CYCLE,
            message=(
                f"Cannot infer scope for components with mutual AUTO "
                f"dependencies: {', '.join(names)}."
            ),
            suggestion=(
                "Set an explicit scope (Scope.SINGLETON or Scope.REQUEST) "
                "on at least one component in the cycle."
            ),
        ),
    ]


def build_graph(
    registrations: dict[tuple[type, str | None], ComponentNode],
) -> list[ResolutionFailure]:
    """Validate the dependency graph and return any failures found.

    Uses Kahn's algorithm for topological sort to detect cycles.
    Collects all failures rather than stopping at the first.
    """
    failures, _order = _build_graph(registrations)
    return failures


def _build_graph(
    registrations: dict[tuple[type, str | None], ComponentNode],
) -> tuple[list[ResolutionFailure], list[tuple[type, str | None]]]:
    """Build and validate the dependency graph.

    Returns (failures, topological_order).  The topological order lists
    dependency keys before their dependents.
    """
    failures: list[ResolutionFailure] = []
    failures.extend(_resolve_auto_scopes(registrations))

    adj: dict[tuple[type, str | None], set[tuple[type, str | None]]] = defaultdict(set)
    in_degree: dict[tuple[type, str | None], int] = {}

    for key in registrations:
        in_degree.setdefault(key, 0)

    for key, node in registrations.items():
        if not node.dependencies:
            target = node.factory if node.factory is not None else node.impl
            node.dependencies = inspect_dependencies(target)
        for dep in node.dependencies:
            dep_key = (dep.required_type, dep.qualifier)

            if (
                dep.is_list
                or dep.env_var is not None
                or (
                    dep.required_type is logging.Logger and dep_key not in registrations
                )
            ):
                continue

            if dep_key not in registrations:
                if dep.optional or dep.has_default:
                    continue
                failures.append(
                    ResolutionFailure(
                        kind=FailureKind.MISSING,
                        message=(
                            f"Missing dependency for {node.impl.__name__}.__init__: "
                            f"parameter '{dep.name}' requires type "
                            f"'{dep.required_type.__name__}'"
                            + (
                                f" with qualifier '{dep.qualifier}'"
                                if dep.qualifier
                                else ""
                            )
                            + ", but no matching component is registered."
                        ),
                        suggestion=(
                            f"Register a component of type "
                            f"{dep.required_type.__name__}"
                            + (
                                f" with qualifier '{dep.qualifier}'"
                                if dep.qualifier
                                else ""
                            )
                            + "."
                        ),
                        component=node.impl,
                        parameter=dep.name,
                    ),
                )
                continue

            dep_node = registrations[dep_key]
            if node.scope is Scope.SINGLETON and dep_node.scope is Scope.REQUEST:
                failures.append(
                    ResolutionFailure(
                        kind=FailureKind.SCOPE_MISMATCH,
                        message=(
                            f"Singleton '{node.impl.__name__}' depends on "
                            f"request-scoped '{dep_node.impl.__name__}' — "
                            f"singletons cannot depend on request-scoped "
                            f"components because they are created at startup "
                            f"before any request context exists."
                        ),
                        suggestion=(
                            f"Change '{node.impl.__name__}' to request scope, "
                            f"or remove the dependency on "
                            f"'{dep_node.impl.__name__}'."
                        ),
                        component=node.impl,
                        parameter=dep.name,
                    ),
                )
                continue

            adj[dep_key].add(key)
            in_degree[key] = in_degree.get(key, 0) + 1

    cycle_failures, order = _detect_cycles(registrations, adj, in_degree)
    failures.extend(cycle_failures)

    return failures, order


def _detect_cycles(
    registrations: dict[tuple[type, str | None], ComponentNode],
    adj: dict[tuple[type, str | None], set[tuple[type, str | None]]],
    in_degree: dict[tuple[type, str | None], int],
) -> tuple[list[ResolutionFailure], list[tuple[type, str | None]]]:
    """Use Kahn's algorithm to detect cycles in the dependency graph.

    Returns a tuple of (failures, topological_order).  The topological order
    lists dependency keys before their dependents so that eager instantiation
    can resolve dependencies in the correct sequence.
    """
    queue: deque[tuple[type, str | None]] = deque()
    for key, degree in in_degree.items():
        if degree == 0:
            queue.append(key)

    order: list[tuple[type, str | None]] = []
    while queue:
        current = queue.popleft()
        order.append(current)
        for neighbor in adj.get(current, set()):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) == len(registrations):
        return [], order

    cycle_nodes = [key for key, degree in in_degree.items() if degree > 0]
    cycle_names = [registrations[key].impl.__name__ for key in cycle_nodes]
    cycle_str = " -> ".join(cycle_names)

    return [
        ResolutionFailure(
            kind=FailureKind.CIRCULAR,
            message=f"Circular dependency detected: {cycle_str}.",
            suggestion=("Break the cycle by introducing an interface or factory."),
        ),
    ], order


def validate_graph(
    registrations: dict[tuple[type, str | None], ComponentNode],
) -> list[tuple[type, str | None]]:
    """Validate the dependency graph, raising on any failures.

    Returns the topological order of registration keys (dependencies before
    dependents) so that callers can instantiate in the correct sequence.
    """
    failures, order = _build_graph(registrations)
    if failures:
        raise DependencyResolutionError(failures)
    return order
