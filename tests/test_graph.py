from __future__ import annotations

import pytest

from uncoiled import (
    ComponentNode,
    DependencyResolutionError,
    FailureKind,
    build_graph,
    validate_graph,
)


def _make_registrations(
    *nodes: ComponentNode,
) -> dict[tuple[type, str | None], ComponentNode]:
    return {(node.provides, node.qualifier): node for node in nodes}


class Repository:
    pass


class UserService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo


class CycleA:
    def __init__(self, b: CycleB) -> None:
        self.b = b


class CycleB:
    def __init__(self, a: CycleA) -> None:
        self.a = a


class TestBuildGraph:
    def test_valid_graph_no_failures(self) -> None:
        registrations = _make_registrations(
            ComponentNode(impl=Repository, provides=Repository),
            ComponentNode(impl=UserService, provides=UserService),
        )
        failures = build_graph(registrations)
        assert failures == []

    def test_missing_dependency(self) -> None:
        registrations = _make_registrations(
            ComponentNode(impl=UserService, provides=UserService),
        )
        failures = build_graph(registrations)
        assert len(failures) == 1
        assert failures[0].kind is FailureKind.MISSING
        assert "Repository" in failures[0].message
        assert failures[0].component is UserService
        assert failures[0].parameter == "repo"

    def test_optional_dependency_not_required(self) -> None:
        class OptService:
            def __init__(self, repo: Repository | None = None) -> None:
                self.repo = repo

        registrations = _make_registrations(
            ComponentNode(impl=OptService, provides=OptService),
        )
        assert build_graph(registrations) == []

    def test_default_dependency_not_required(self) -> None:
        class DefaultService:
            def __init__(self, name: str = "default") -> None:
                self.name = name

        registrations = _make_registrations(
            ComponentNode(impl=DefaultService, provides=DefaultService),
        )
        assert build_graph(registrations) == []

    def test_circular_dependency(self) -> None:
        registrations = _make_registrations(
            ComponentNode(impl=CycleA, provides=CycleA),
            ComponentNode(impl=CycleB, provides=CycleB),
        )
        failures = build_graph(registrations)
        assert any(f.kind is FailureKind.CIRCULAR for f in failures)

    def test_list_dependency_not_required(self) -> None:
        class MultiService:
            def __init__(self, repos: list[Repository]) -> None:
                self.repos = repos

        registrations = _make_registrations(
            ComponentNode(impl=MultiService, provides=MultiService),
        )
        assert build_graph(registrations) == []

    def test_multiple_failures_collected(self) -> None:
        class NeedsBoth:
            def __init__(self, a: Repository, b: UserService) -> None:
                self.a = a
                self.b = b

        registrations = _make_registrations(
            ComponentNode(impl=NeedsBoth, provides=NeedsBoth),
        )
        failures = build_graph(registrations)
        expected = 2
        assert len(failures) == expected


class TestValidateGraph:
    def test_raises_on_failure(self) -> None:
        registrations = _make_registrations(
            ComponentNode(impl=UserService, provides=UserService),
        )
        with pytest.raises(DependencyResolutionError) as exc_info:
            validate_graph(registrations)
        assert len(exc_info.value.failures) == 1

    def test_passes_valid_graph(self) -> None:
        registrations = _make_registrations(
            ComponentNode(impl=Repository, provides=Repository),
            ComponentNode(impl=UserService, provides=UserService),
        )
        validate_graph(registrations)
