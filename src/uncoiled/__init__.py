from __future__ import annotations

import os
import typing as tp
from abc import ABCMeta
from collections import defaultdict
from copy import deepcopy
from functools import partial, partialmethod
from inspect import isclass

import typing_extensions as tx

RETURN_ANNOTATION = "return"

P = tx.ParamSpec("P")
S = tp.TypeVar("S", bound=str)
T = tp.TypeVar("T")


class EnvVar(tp.Mapping[str, tp.Optional[str]], tp.Generic[S], metaclass=ABCMeta):
    pass


class Every(tp.Sequence[T], tp.Generic[T], metaclass=ABCMeta):
    pass


Registrations = tp.MutableMapping[str, tp.List[tp.Callable[P, T]]]


class Container:

    _registrations: Registrations

    def __init__(self, registrations: tp.Optional[Registrations] = None):
        if registrations is None:
            registrations = defaultdict(list)
            registrations[self._canonical_name(EnvVar)].append(lambda: os.environ)
        self._registrations = registrations

    def get(self, type_: tp.Type[T]) -> T:
        multi = False
        if tp.get_origin(type_) is Every:
            (type_,) = tp.get_args(type_)
            multi = True
        name = self._canonical_name(type_)
        target, prop = name.rsplit(".", 1) if "." in name else (name, None)
        if target == self._canonical_name(EnvVar):
            return self.get(EnvVar).get(prop)
        creations = self._registrations.get(name)
        if creations is None:
            raise TypeError(f"type {name!r} is not registered")
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
        with_factory: tp.Callable[..., tp.Any],
    ) -> Container:
        targets = self._target_types(create)
        registrations = deepcopy(self._registrations)
        for target in targets:
            registrations[self._canonical_name(target)] = [with_factory]
        return type(self)(registrations)

    def register(self, create: tp.Callable[P, T]) -> tp.Callable[[], T]:
        targets = self._target_types(create)
        for target in targets:
            self._registrations[self._canonical_name(target)].append(create)
        return partial(self.get, type_=targets[0])

    def _resolve(self, create: tp.Type[T]) -> tp.Mapping[str, T]:
        return {
            key: self.get(value) for key, value in self._requirements(create).items()
        }

    @classmethod
    def _canonical_name(cls, obj: tp.Any) -> str:
        """Get the fully-qualified name of an object."""
        name = None
        if hasattr(obj, "__metadata__"):
            if tp.get_origin(obj.__metadata__[0]) is EnvVar:
                var_name = tp.get_args(obj.__metadata__[0])[0].__forward_arg__
                name = f"{cls._canonical_name(EnvVar)}.{var_name}"
            else:
                raise NotImplementedError(
                    "other Annotated types are not currently handled"
                )
        if isinstance(obj, (partial, partialmethod)):
            obj = obj.keywords["type_"]
        module = obj.__module__
        if name is None:
            if not hasattr(obj, "__qualname__"):
                raise TypeError(
                    f"cannot determine canonical name for {obj!r} in {module}"
                )
            name = obj.__qualname__
        return name if module == "builtins" else f"{module}.{name}"

    @staticmethod
    def _requirements(obj: tp.Any) -> tp.Mapping[str, tp.Type[T]]:
        """Get a mapping of argument names to requirement types."""
        if isclass(obj):
            obj = obj.__init__
        return {
            key: value
            for key, value in tp.get_type_hints(obj).items()
            if key != RETURN_ANNOTATION
        }

    @staticmethod
    def _target_types(
        obj: tp.Union[tp.Type[T], tp.Callable[..., T]],
    ) -> tp.List[tp.Type[T]]:
        """Get the target type of the object.

        - Classes provide their instances
        - Functions provide their return types

        """
        if obj is EnvVar:
            return [EnvVar]
        if isclass(obj):
            return [cls for cls in obj.mro() if cls is not object]
        return [obj.__annotations__[RETURN_ANNOTATION]]


_default_container = Container()


def get(type_: tp.Type[T]) -> T:
    return _default_container.get(type_)


def inject(func: tp.Callable[P, T]) -> tp.Callable[[], T]:
    return _default_container.inject(func)


def overload(
    create: tp.Callable[P, T],
    *,
    with_factory: tp.Callable[P, T],
) -> Container:
    return _default_container.overload(create, with_factory)


def register(create: tp.Callable[P, T]) -> tp.Callable[P, T]:
    """Register the class or function as a factory."""
    _default_container.register(create)
    return create
