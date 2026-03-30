"""Dependency graph visualisation — renders registrations as Mermaid diagrams."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ._inspection import inspect_dependencies
from ._types import Scope

if TYPE_CHECKING:
    from ._graph import ComponentNode


def _node_id(type_: type, qualifier: str | None) -> str:
    """Create a stable Mermaid node ID from a type and qualifier."""
    name = type_.__name__
    if qualifier:
        return f"{name}_{qualifier}"
    return name


def _node_label(node: ComponentNode) -> str:
    """Create a display label for a node, showing scope and qualifier."""
    name = node.impl.__name__
    parts: list[str] = []
    if node.provides is not node.impl:
        parts.append(f"as {node.provides.__name__}")
    if node.qualifier:
        parts.append(f"qualifier={node.qualifier}")
    if node.scope is not Scope.SINGLETON:
        parts.append(node.scope.value)
    if parts:
        return f'"{name}<br/>({", ".join(parts)})"'
    return name


def _scope_class(scope: Scope) -> str:
    """Map scope to a Mermaid CSS class name."""
    return f"scope_{scope.value}"


def render_mermaid(
    registrations: dict[tuple[type, str | None], ComponentNode],
) -> str:
    """Render the dependency graph as a Mermaid flowchart.

    Returns a string suitable for embedding in Markdown::

        ```mermaid
        container.visualise()
        ```
    """
    lines: list[str] = ["graph TD"]

    # Define nodes
    for (type_, qualifier), node in registrations.items():
        nid = _node_id(type_, qualifier)
        label = _node_label(node)
        lines.append(f"    {nid}[{label}]:::{_scope_class(node.scope)}")

    # Define edges
    for (type_, qualifier), node in registrations.items():
        target_id = _node_id(type_, qualifier)
        deps = node.dependencies
        if not deps:
            factory = node.factory if node.factory is not None else node.impl
            deps = inspect_dependencies(factory)
        for dep in deps:
            if dep.env_var is not None:
                env_id = f"env_{dep.env_var}"
                lines.append(f"    {env_id}[/{dep.env_var}/]:::env_var")
                style = "-.->" if dep.has_default else "-->"
                lines.append(f"    {env_id} {style} {target_id}")
                continue

            if dep.required_type is logging.Logger:
                lines.append("    Logger[/Logger/]:::env_var")
                lines.append(f"    Logger -.-> {target_id}")
                continue

            dep_key = (dep.required_type, dep.qualifier)
            if dep_key in registrations:
                dep_id = _node_id(dep.required_type, dep.qualifier)
                style = "-.->" if dep.optional or dep.has_default else "-->"
                lines.append(f"    {dep_id} {style} {target_id}")

    # Style definitions
    lines.append("")
    lines.append(f"    classDef {_scope_class(Scope.SINGLETON)} fill:#4a9,stroke:#333")
    lines.append(f"    classDef {_scope_class(Scope.TRANSIENT)} fill:#f96,stroke:#333")
    lines.append(f"    classDef {_scope_class(Scope.REQUEST)} fill:#69f,stroke:#333")
    lines.append(f"    classDef {_scope_class(Scope.AUTO)} fill:#ccc,stroke:#333")
    lines.append("    classDef env_var fill:#ff9,stroke:#333")

    return "\n".join(lines)
