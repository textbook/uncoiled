from typing import Annotated, Optional, Union

import pytest

from tests._future_annotations_helpers import (
    ChildConfig,
    ForwardRefService,
    LateDefinedClass,
    OptionalService,
)
from tests._future_annotations_helpers import Repository as FutureRepo
from tests._future_annotations_helpers import UserService as FutureService
from uncoiled import DependencySpec, Qualifier, inspect_dependencies


class Repository:
    pass


class UserService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo


class OptionalDep:
    def __init__(self, repo: Repository | None) -> None:
        self.repo = repo


class ListDep:
    def __init__(self, repos: list[Repository]) -> None:
        self.repos = repos


class QualifiedDep:
    def __init__(
        self,
        repo: Annotated[Repository, Qualifier("postgres")],
    ) -> None:
        self.repo = repo


class DefaultDep:
    def __init__(self, name: str = "default") -> None:
        self.name = name


class NoDeps:
    pass


class NoAnnotations:
    def __init__(self, x) -> None:  # noqa: ANN001
        self.x = x


class TestInspectDependencies:
    def test_single_dependency(self) -> None:
        specs = inspect_dependencies(UserService)
        assert specs == [
            DependencySpec(name="repo", required_type=Repository),
        ]

    def test_optional_dependency(self) -> None:
        specs = inspect_dependencies(OptionalDep)
        assert specs == [
            DependencySpec(
                name="repo",
                required_type=Repository,
                optional=True,
            ),
        ]

    def test_list_dependency(self) -> None:
        specs = inspect_dependencies(ListDep)
        assert specs == [
            DependencySpec(
                name="repos",
                required_type=Repository,
                is_list=True,
            ),
        ]

    def test_qualified_dependency(self) -> None:
        specs = inspect_dependencies(QualifiedDep)
        assert specs == [
            DependencySpec(
                name="repo",
                required_type=Repository,
                qualifier="postgres",
            ),
        ]

    def test_default_value(self) -> None:
        specs = inspect_dependencies(DefaultDep)
        assert specs == [
            DependencySpec(
                name="name",
                required_type=str,
                has_default=True,
            ),
        ]

    def test_no_init(self) -> None:
        assert inspect_dependencies(NoDeps) == []

    def test_unannotated_params_skipped(self) -> None:
        assert inspect_dependencies(NoAnnotations) == []

    def test_multiple_dependencies(self) -> None:
        class Multi:
            def __init__(
                self,
                repo: Repository,
                name: str = "x",
                other: Repository | None = None,
            ) -> None:
                self.repo = repo
                self.name = name
                self.other = other

        specs = inspect_dependencies(Multi)
        expected = 3
        assert len(specs) == expected
        assert specs[0].name == "repo"
        assert not specs[0].optional
        assert specs[1].name == "name"
        assert specs[1].has_default
        assert specs[2].name == "other"
        assert specs[2].optional

    def test_unannotated_param_does_not_block_later_params(self) -> None:
        """Skipping an unannotated param should still process subsequent ones."""

        class Mixed:
            def __init__(self, x, repo: Repository, name: str = "hi") -> None:  # noqa: ANN001
                self.x = x
                self.repo = repo
                self.name = name

        specs = inspect_dependencies(Mixed)
        expected = 2
        assert len(specs) == expected
        assert specs[0].name == "repo"
        assert specs[1].name == "name"

    def test_annotated_with_multiple_qualifiers_uses_first(self) -> None:
        """When multiple Qualifiers are in Annotated metadata, the first wins."""

        class MultiQual:
            def __init__(
                self,
                repo: Annotated[Repository, Qualifier("first"), Qualifier("second")],
            ) -> None:
                self.repo = repo

        specs = inspect_dependencies(MultiQual)
        assert len(specs) == 1
        assert specs[0].qualifier == "first"

    def test_optional_dep_marked_optional(self) -> None:
        class Svc:
            def __init__(self, repo: Repository | None) -> None:
                self.repo = repo

        specs = inspect_dependencies(Svc)
        assert len(specs) == 1
        assert specs[0].optional is True

    def test_optional_typing_form(self) -> None:
        """typing.Optional[T] should be handled the same as T | None."""

        class Svc:
            def __init__(self, repo: Optional[Repository]) -> None:  # noqa: UP045
                self.repo = repo

        specs = inspect_dependencies(Svc)
        assert len(specs) == 1
        assert specs[0].required_type is Repository
        assert specs[0].optional is True

    def test_multi_union_not_unwrapped(self) -> None:
        """Union[A, B] (no None) should not be treated as optional."""

        class Svc:
            def __init__(self, thing: Union[Repository, UserService]) -> None:  # noqa: UP007
                self.thing = thing

        specs = inspect_dependencies(Svc)
        assert specs == []

    def test_three_arg_union_with_none_not_unwrapped(self) -> None:
        """Union[A, B, None] should not be unwrapped to a single type."""

        class Svc:
            def __init__(
                self,
                thing: Union[Repository, UserService, None],  # noqa: UP007
            ) -> None:
                self.thing = thing

        specs = inspect_dependencies(Svc)
        assert specs == []

    def test_annotated_optional_with_qualifier(self) -> None:
        """Annotated[Optional[T], Qualifier] should be optional with qualifier."""

        class Svc:
            def __init__(
                self,
                repo: Annotated[Repository | None, Qualifier("pg")],
            ) -> None:
                self.repo = repo

        specs = inspect_dependencies(Svc)
        assert len(specs) == 1
        assert specs[0].required_type is Repository
        assert specs[0].optional is True
        assert specs[0].qualifier == "pg"

    def test_annotated_list_extracts_inner_type(self) -> None:
        """Annotated[list[T], Qualifier] should extract T."""

        class Svc:
            def __init__(
                self,
                repos: Annotated[list[Repository], Qualifier("all")],
            ) -> None:
                self.repos = repos

        specs = inspect_dependencies(Svc)
        assert len(specs) == 1
        assert specs[0].required_type is Repository
        assert specs[0].is_list is True
        assert specs[0].qualifier == "all"

    def test_new_style_union_optional(self) -> None:
        """T | None (types.UnionType) should unwrap to T."""

        class Svc:
            def __init__(self, repo: Repository | None) -> None:
                self.repo = repo

        specs = inspect_dependencies(Svc)
        assert len(specs) == 1
        assert specs[0].required_type is Repository
        assert specs[0].optional is True

    def test_old_and_new_union_in_same_class(self) -> None:
        """Both typing.Optional and T | None should work in the same class."""

        class Svc:
            def __init__(
                self,
                old: Optional[Repository],  # noqa: UP045
                new: UserService | None,
            ) -> None:
                self.old = old
                self.new = new

        specs = inspect_dependencies(Svc)
        expected = 2
        assert len(specs) == expected
        assert specs[0].required_type is Repository
        assert specs[0].optional is True
        assert specs[1].required_type is UserService
        assert specs[1].optional is True

    def test_dependency_spec_is_frozen(self) -> None:
        spec = DependencySpec(name="x", required_type=Repository)
        with pytest.raises(AttributeError):
            spec.name = "y"  # ty: ignore[invalid-assignment]

    def test_annotated_with_non_qualifier_metadata_ignored(self) -> None:
        """Non-Qualifier metadata in Annotated should be skipped."""

        class Svc:
            def __init__(
                self,
                repo: Annotated[Repository, "some_string", Qualifier("pg")],
            ) -> None:
                self.repo = repo

        specs = inspect_dependencies(Svc)
        assert len(specs) == 1
        assert specs[0].qualifier == "pg"
        assert specs[0].required_type is Repository

    def test_future_annotations_resolves_types(self) -> None:
        """Classes using ``from __future__ import annotations`` should work."""
        specs = inspect_dependencies(FutureService)
        assert len(specs) == 1
        assert specs[0].name == "repo"
        assert specs[0].required_type is FutureRepo

    def test_future_annotations_optional(self) -> None:
        specs = inspect_dependencies(OptionalService)
        assert len(specs) == 1
        assert specs[0].required_type is FutureRepo
        assert specs[0].optional is True

    def test_future_annotations_forward_ref(self) -> None:
        specs = inspect_dependencies(ForwardRefService)
        assert len(specs) == 1
        assert specs[0].required_type is LateDefinedClass

    def test_future_annotations_dataclass_inheritance(self) -> None:
        specs = inspect_dependencies(ChildConfig)
        field_names = {s.name for s in specs}
        assert "host" in field_names
        assert "port" in field_names
        assert "name" in field_names

    def test_function_inspection(self) -> None:
        def factory(repo: Repository, name: str = "x") -> UserService:
            _ = name
            return UserService(repo)

        specs = inspect_dependencies(factory)
        expected = 2
        assert len(specs) == expected
        assert specs[0].name == "repo"
        assert specs[1].has_default is True

    def test_pep695_typevar_param_skipped(self) -> None:
        """TypeVar parameters are not concrete types and should be skipped."""

        class Handler[T]:
            def __init__(self, item: T) -> None:
                self.item = item

        specs = inspect_dependencies(Handler)
        assert len(specs) == 0

    def test_pep695_concrete_subclass_inherits_typevar(self) -> None:
        """Concrete subclass inherits __init__ with TypeVar — still skipped."""

        class Handler[T]:
            def __init__(self, item: T) -> None:
                self.item = item

        class RepoHandler(Handler[Repository]):
            pass

        # TypeVar T in the inherited __init__ is not resolved to Repository
        specs = inspect_dependencies(RepoHandler)
        assert len(specs) == 0

    def test_pep695_generic_with_concrete_deps(self) -> None:
        """Concrete deps alongside TypeVar params are resolved normally."""

        class Service[T]:
            def __init__(self, repo: Repository, config: T) -> None:
                self.repo = repo
                self.config = config

        specs = inspect_dependencies(Service)
        assert len(specs) == 1
        assert specs[0].name == "repo"
        assert specs[0].required_type is Repository
