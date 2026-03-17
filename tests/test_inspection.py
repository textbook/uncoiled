from typing import Annotated

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
