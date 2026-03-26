"""Introspection engine for extracting dependencies from ``__init__`` signatures."""

from __future__ import annotations

import inspect
import types
from dataclasses import dataclass
from typing import Annotated, Union, get_args, get_origin

from ._envvar import EnvVar
from ._qualifiers import Qualifier

_OPTIONAL_UNION_ARGS = 2


@dataclass(frozen=True)
class DependencySpec:
    """A single dependency extracted from an ``__init__`` parameter."""

    name: str
    required_type: type
    optional: bool = False
    is_list: bool = False
    qualifier: str | None = None
    has_default: bool = False
    env_var: str | None = None


def _is_optional_union(annotation: object) -> type | None:
    """Check if an annotation is ``T | None`` or ``Optional[T]`` and return T."""
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        args = get_args(annotation)
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1 and len(args) == _OPTIONAL_UNION_ARGS:
            return non_none[0]
    return None


def inspect_dependencies(target: object) -> list[DependencySpec]:
    """Extract dependency specifications from a callable's parameters.

    For classes, inspects ``__init__``. For functions, inspects the
    function signature directly.
    """
    if isinstance(target, type):
        func = target.__init__
    elif callable(target):
        func = target
    else:
        return []

    try:
        hints = inspect.get_annotations(func, eval_str=True)
    except Exception:  # noqa: BLE001
        return []

    sig = inspect.signature(func)
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


def _resolve_annotated(
    name: str,
    args: tuple[object, ...],
    *,
    has_default: bool,
) -> DependencySpec | None:
    """Resolve an ``Annotated[T, ...]`` annotation."""
    inner = args[0]
    qualifier = None
    env_var = None
    for meta in args[1:]:
        if isinstance(meta, Qualifier) and qualifier is None:
            qualifier = meta.name
        elif isinstance(meta, EnvVar) and env_var is None:
            env_var = meta.name
    if env_var is not None:
        return DependencySpec(
            name=name,
            required_type=inner if isinstance(inner, type) else type(inner),
            has_default=has_default,
            env_var=env_var,
        )
    return _resolve_annotation_with_qualifier(
        name,
        inner,
        qualifier=qualifier,
        has_default=has_default,
    )


def _resolve_annotation(
    name: str,
    annotation: object,
    *,
    has_default: bool,
) -> DependencySpec | None:
    """Resolve a single annotation into a DependencySpec."""
    if get_origin(annotation) is Annotated:
        return _resolve_annotated(
            name,
            get_args(annotation),
            has_default=has_default,
        )

    return _resolve_annotation_with_qualifier(
        name,
        annotation,
        qualifier=None,
        has_default=has_default,
    )


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
