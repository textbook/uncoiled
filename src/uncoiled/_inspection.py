"""Introspection engine for extracting dependencies from ``__init__`` signatures."""

from __future__ import annotations

import inspect
import types
from dataclasses import dataclass
from typing import Annotated, Union, get_args, get_origin

from ._qualifiers import Qualifier


@dataclass(frozen=True)
class DependencySpec:
    """A single dependency extracted from an ``__init__`` parameter."""

    name: str
    required_type: type
    optional: bool = False
    is_list: bool = False
    qualifier: str | None = None
    has_default: bool = False


def _is_optional_union(annotation: object) -> type | None:
    """Check if an annotation is ``T | None`` or ``Optional[T]`` and return T."""
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        args = get_args(annotation)
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1 and len(args) == 2:  # noqa: PLR2004
            return non_none[0]
    return None


def inspect_dependencies(cls: type) -> list[DependencySpec]:
    """Extract dependency specifications from a class's ``__init__`` parameters.

    Inspects the ``__init__`` signature and type annotations to determine
    what dependencies a class requires for construction.
    """
    try:
        hints = inspect.get_annotations(cls.__init__, eval_str=True)
    except Exception:  # noqa: BLE001
        return []

    sig = inspect.signature(cls.__init__)
    specs: list[DependencySpec] = []

    for name, param in sig.parameters.items():
        if name == "self":
            continue

        annotation = hints.get(name)
        if annotation is None:
            continue

        has_default = param.default is not inspect.Parameter.empty

        spec = _resolve_annotation(name, annotation, has_default=has_default)
        if spec is not None:
            specs.append(spec)

    return specs


def _resolve_annotation(
    name: str,
    annotation: object,
    *,
    has_default: bool,
) -> DependencySpec | None:
    """Resolve a single annotation into a DependencySpec."""
    origin = get_origin(annotation)

    if origin is Annotated:
        args = get_args(annotation)
        inner = args[0]
        qualifier = None
        for meta in args[1:]:
            if isinstance(meta, Qualifier):
                qualifier = meta.name
                break
        return _resolve_annotation_with_qualifier(
            name,
            inner,
            qualifier=qualifier,
            has_default=has_default,
        )

    if origin is list:
        args = get_args(annotation)
        if args:
            return DependencySpec(
                name=name,
                required_type=args[0],
                is_list=True,
                has_default=has_default,
            )
        return None

    inner = _is_optional_union(annotation)
    if inner is not None:
        return DependencySpec(
            name=name,
            required_type=inner,
            optional=True,
            has_default=has_default,
        )

    if isinstance(annotation, type):
        return DependencySpec(
            name=name,
            required_type=annotation,
            has_default=has_default,
        )

    return None


def _resolve_annotation_with_qualifier(
    name: str,
    inner: object,
    *,
    qualifier: str | None,
    has_default: bool,
) -> DependencySpec | None:
    """Resolve inner type of an Annotated, carrying qualifier through."""
    optional_inner = _is_optional_union(inner)
    if optional_inner is not None:
        return DependencySpec(
            name=name,
            required_type=optional_inner,
            optional=True,
            qualifier=qualifier,
            has_default=has_default,
        )

    if get_origin(inner) is list:
        args = get_args(inner)
        if args:
            return DependencySpec(
                name=name,
                required_type=args[0],
                is_list=True,
                qualifier=qualifier,
                has_default=has_default,
            )
        return None

    if isinstance(inner, type):
        return DependencySpec(
            name=name,
            required_type=inner,
            qualifier=qualifier,
            has_default=has_default,
        )

    return None
