"""Dependency graph builder with cycle detection and validation."""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field

from ._errors import DependencyResolutionError, FailureKind, ResolutionFailure
from ._inspection import DependencySpec, inspect_dependencies
from ._types import Scope


@dataclass
class ComponentNode:
    """A node in the dependency graph representing a registered component."""

    impl: type
    provides: type
    qualifier: str | None = None
    dependencies: list[DependencySpec] = field(default_factory=list)
    scope: Scope = Scope.SINGLETON
    factory: object | None = None


def _type_key(typ: type, qualifier: str | None = None) -> tuple[type, str | None]:
    return (typ, qualifier)


def build_graph(
    registrations: dict[tuple[type, str | None], ComponentNode],
) -> list[ResolutionFailure]:
    """Validate the dependency graph and return any failures found.

    Uses Kahn's algorithm for topological sort to detect cycles.
    Collects all failures rather than stopping at the first.
    """
    failures: list[ResolutionFailure] = []

    all_providers: dict[type, list[ComponentNode]] = defaultdict(list)
    for node in registrations.values():
        all_providers[node.provides].append(node)

    adj: dict[tuple[type, str | None], set[tuple[type, str | None]]] = defaultdict(set)
    in_degree: dict[tuple[type, str | None], int] = {}

    for key in registrations:
        in_degree.setdefault(key, 0)

    for key, node in registrations.items():
        target = node.factory if node.factory is not None else node.impl
        node.dependencies = inspect_dependencies(target)
        for dep in node.dependencies:
            dep_key = _type_key(dep.required_type, dep.qualifier)

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

    cycle_failures = _detect_cycles(registrations, adj, in_degree)
    failures.extend(cycle_failures)

    return failures


def _detect_cycles(
    registrations: dict[tuple[type, str | None], ComponentNode],
    adj: dict[tuple[type, str | None], set[tuple[type, str | None]]],
    in_degree: dict[tuple[type, str | None], int],
) -> list[ResolutionFailure]:
    """Use Kahn's algorithm to detect cycles in the dependency graph."""
    queue: deque[tuple[type, str | None]] = deque()
    for key, degree in in_degree.items():
        if degree == 0:
            queue.append(key)

    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for neighbor in adj.get(current, set()):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited == len(registrations):
        return []

    cycle_nodes = [key for key, degree in in_degree.items() if degree > 0]
    cycle_names = [registrations[key].impl.__name__ for key in cycle_nodes]
    cycle_str = " -> ".join(cycle_names)

    return [
        ResolutionFailure(
            kind=FailureKind.CIRCULAR,
            message=f"Circular dependency detected: {cycle_str}.",
            suggestion=("Break the cycle by introducing an interface or factory."),
        ),
    ]


def validate_graph(
    registrations: dict[tuple[type, str | None], ComponentNode],
) -> None:
    """Validate the dependency graph, raising on any failures."""
    failures = build_graph(registrations)
    if failures:
        raise DependencyResolutionError(failures)
