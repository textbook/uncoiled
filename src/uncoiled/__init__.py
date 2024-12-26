from __future__ import annotations

import typing as tp
from collections import defaultdict
from copy import deepcopy
from functools import partial, partialmethod
from inspect import isclass

from typing_extensions import ParamSpec

RETURN_ANNOTATION = "return"

P = ParamSpec("P")
T = tp.TypeVar("T")


class Every(tp.Sequence[T], tp.Generic[T]):
    pass


Registrations = tp.MutableMapping[str, tp.List[tp.Callable[P, T]]]


class Container:

    _registrations: Registrations

    def __init__(self, registrations: tp.Optional[Registrations] = None):
        self._registrations = registrations or defaultdict(list)

    def get(self, type_: tp.Type[T]) -> T:
        multi = False
        if tp.get_origin(type_) is Every:
            type_, = tp.get_args(type_)
            multi = True
        created = [
            partial(create, **self._resolve(create))
            for create in self._registrations.get(_name(type_))
        ]
        return [create() for create in created] if multi else created[0]()

    def overload(
        self,
        create: tp.Callable[P, T],
        with_factory: tp.Callable[P, T],
    ) -> Container:
        target = _target_type(create)
        registrations = deepcopy(self._registrations)
        registrations[_name(target)] = [with_factory]
        return type(self)(registrations)

    def register(self, create: tp.Callable[P, T]) -> tp.Callable[[], T]:
        target = _target_type(create)
        self._registrations[_name(target)].append(create)
        return partial(self.get, type_=target)

    def _resolve(self, create: tp.Type[T]) -> tp.Mapping[str, T]:
        return {
            key: self.get(value)
            for key, value in _annotations(create).items()
            if key != RETURN_ANNOTATION
        }


_default_container = Container()


def get(type_: tp.Type[T]) -> T:
    return _default_container.get(type_)


def factory(create: tp.Callable[P, T]) -> tp.Callable[P, T]:
    """Register the class or function as a factory."""
    _default_container.register(create)
    return create


def overload(
    create: tp.Callable[P, T],
    *,
    with_factory: tp.Callable[P, T],
) -> Container:
    return _default_container.overload(create, with_factory)


def _annotations(obj: tp.Any) -> tp.Mapping[str, tp.Type[T]]:
    if isclass(obj):
        obj = obj.__init__
    return tp.get_type_hints(obj)


def _name(obj: tp.Any) -> str:
    """Get the fully-qualified name of an object."""
    if isinstance(obj, (partial, partialmethod)):
        obj = obj.keywords["type_"]
    module = obj.__module__
    if module == "builtins":
        return obj.__qualname__
    return f"{module}.{obj.__qualname__}"


def _target_type(obj: tp.Any) -> T:
    """Get the target type of the object.

    - Classes provide their instances
    - Functions provide their return types

    """
    return obj if isclass(obj) else obj.__annotations__[RETURN_ANNOTATION]
