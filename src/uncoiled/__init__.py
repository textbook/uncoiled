from __future__ import annotations

import typing as tp
from abc import ABCMeta
from collections import defaultdict
from copy import deepcopy
from functools import partial, partialmethod
from inspect import isclass

import typing_extensions as tx

RETURN_ANNOTATION = "return"

P = tx.ParamSpec("P")
T = tp.TypeVar("T")


class Every(tp.Sequence[T], tp.Generic[T], metaclass=ABCMeta):
    pass


Registrations = tp.MutableMapping[str, tp.List[tp.Callable[P, T]]]


class Container:

    _registrations: Registrations

    def __init__(self, registrations: tp.Optional[Registrations] = None):
        self._registrations = registrations or defaultdict(list)

    def get(self, type_: tp.Type[T]) -> T:
        multi = False
        if tp.get_origin(type_) is Every:
            (type_,) = tp.get_args(type_)
            multi = True
        creations = self._registrations.get(_name(type_))
        if creations is None:
            raise TypeError(f"type {_name(type_)!r} is not registered")
        created = [partial(create, **self._resolve(create)) for create in creations]
        return [create() for create in created] if multi else created[0]()

    def inject(
        self,
        func: tp.Callable[P, T],
    ) -> tp.Callable[[], T]:
        return partial(func, **self._resolve(func))

    def overload(
        self,
        create: tp.Callable[P, T],
        with_factory: tp.Callable[P, T],
    ) -> Container:
        targets = _target_types(create)
        registrations = deepcopy(self._registrations)
        for target in targets:
            registrations[_name(target)] = [with_factory]
        return type(self)(registrations)

    def register(self, create: tp.Callable[P, T]) -> tp.Callable[[], T]:
        targets = _target_types(create)
        for target in targets:
            self._registrations[_name(target)].append(create)
        return partial(self.get, type_=targets[0])

    def _resolve(self, create: tp.Type[T]) -> tp.Mapping[str, T]:
        return {
            key: self.get(value)
            for key, value in _annotations(create).items()
            if key != RETURN_ANNOTATION
        }


_default_container = Container()


def get(type_: tp.Type[T]) -> T:
    return _default_container.get(type_)


def inject(func: tp.Callable[P, T]) -> tp.Callable[[], T]:
    return _default_container.inject(func)


def register(create: tp.Callable[P, T]) -> tp.Callable[P, T]:
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


def _target_types(
    obj: tp.Union[tp.Type[T], tp.Callable[..., T]],
) -> tp.List[tp.Type[T]]:
    """Get the target type of the object.

    - Classes provide their instances
    - Functions provide their return types

    """
    if isclass(obj):
        return [cls for cls in obj.mro() if cls is not object]
    return [obj.__annotations__[RETURN_ANNOTATION]]
