from __future__ import annotations

from typing import Annotated

import pytest

from uncoiled import (
    ComponentNode,
    DependencyResolutionError,
    FailureKind,
    Qualifier,
    Scope,
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


class ExtraService:
    pass


class NeedsOptThenReq:
    def __init__(self, opt: Repository | None, req: ExtraService) -> None:
        self.opt = opt
        self.req = req


class RequestDep:
    pass


class SingletonNeedsRequest:
    def __init__(self, dep: RequestDep) -> None:
        self.dep = dep


class RequestNeedsRequest:
    def __init__(self, dep: RequestDep) -> None:
        self.dep = dep


class TransientNeedsRequest:
    def __init__(self, dep: RequestDep) -> None:
        self.dep = dep


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

    def test_list_dep_does_not_block_subsequent_deps(self) -> None:
        """A list dep followed by a required dep must still validate the latter."""

        class Aggregator:
            def __init__(self, repos: list[Repository], svc: UserService) -> None:
                self.repos = repos
                self.svc = svc

        registrations = _make_registrations(
            ComponentNode(impl=Aggregator, provides=Aggregator),
        )
        failures = build_graph(registrations)
        assert len(failures) == 1
        assert failures[0].kind is FailureKind.MISSING
        assert "UserService" in failures[0].message

    def test_optional_dep_does_not_block_subsequent_deps(self) -> None:
        """An optional dep followed by a required dep must still validate the latter."""

        class Combo:
            def __init__(
                self,
                opt: Repository | None = None,
                required: UserService = ...,  # ty: ignore[invalid-parameter-default]
            ) -> None:
                self.opt = opt
                self.required = required

        registrations = _make_registrations(
            ComponentNode(impl=UserService, provides=UserService),
            ComponentNode(impl=Combo, provides=Combo),
        )
        # UserService itself needs Repository which is missing
        failures = build_graph(registrations)
        assert any(f.kind is FailureKind.MISSING for f in failures)
        assert any("Repository" in f.message for f in failures)

    def test_missing_qualified_dep_includes_qualifier_in_message(self) -> None:
        class QualService:
            def __init__(
                self,
                repo: Annotated[Repository, Qualifier("primary")],
            ) -> None:
                self.repo = repo

        registrations = _make_registrations(
            ComponentNode(impl=QualService, provides=QualService),
        )
        failures = build_graph(registrations)
        assert len(failures) == 1
        assert "primary" in failures[0].message
        assert "primary" in failures[0].suggestion

    def test_diamond_dependency_validates(self) -> None:
        """A diamond graph (A->B, A->C, B->D, C->D) should validate."""

        class D:
            pass

        class B:
            def __init__(self, d: D) -> None:
                self.d = d

        class C:
            def __init__(self, d: D) -> None:
                self.d = d

        class A:
            def __init__(self, b: B, c: C) -> None:
                self.b = b
                self.c = c

        registrations = _make_registrations(
            ComponentNode(impl=D, provides=D),
            ComponentNode(impl=B, provides=B),
            ComponentNode(impl=C, provides=C),
            ComponentNode(impl=A, provides=A),
        )
        assert build_graph(registrations) == []

    def test_cycle_detection_reports_cycle_nodes(self) -> None:
        registrations = _make_registrations(
            ComponentNode(impl=CycleA, provides=CycleA),
            ComponentNode(impl=CycleB, provides=CycleB),
        )
        failures = build_graph(registrations)
        circular = [f for f in failures if f.kind is FailureKind.CIRCULAR]
        assert len(circular) == 1
        assert "CycleA" in circular[0].message
        assert "CycleB" in circular[0].message

    def test_no_false_positive_cycle_in_large_graph(self) -> None:
        """A long chain A->B->C->D->E should not falsely detect a cycle."""

        class E:
            pass

        class D:
            def __init__(self, e: E) -> None:
                self.e = e

        class C:
            def __init__(self, d: D) -> None:
                self.d = d

        class B:
            def __init__(self, c: C) -> None:
                self.c = c

        class A:
            def __init__(self, b: B) -> None:
                self.b = b

        registrations = _make_registrations(
            ComponentNode(impl=E, provides=E),
            ComponentNode(impl=D, provides=D),
            ComponentNode(impl=C, provides=C),
            ComponentNode(impl=B, provides=B),
            ComponentNode(impl=A, provides=A),
        )
        assert build_graph(registrations) == []

    def test_unregistered_optional_does_not_block_required_failure(self) -> None:
        """An unregistered optional dep followed by an unregistered required dep.

        The continue on the optional skip (L60) must not become a break,
        otherwise the required dep failure would go unreported.
        """
        registrations = _make_registrations(
            ComponentNode(impl=NeedsOptThenReq, provides=NeedsOptThenReq),
        )
        failures = build_graph(registrations)
        assert len(failures) == 1
        assert failures[0].kind is FailureKind.MISSING
        assert "ExtraService" in failures[0].message


class TestScopeMismatch:
    def test_singleton_depending_on_request_scoped_fails_validation(self) -> None:
        """A singleton cannot depend on a request-scoped component."""
        registrations = _make_registrations(
            ComponentNode(
                impl=RequestDep,
                provides=RequestDep,
                scope=Scope.REQUEST,
            ),
            ComponentNode(
                impl=SingletonNeedsRequest,
                provides=SingletonNeedsRequest,
                scope=Scope.SINGLETON,
            ),
        )
        failures = build_graph(registrations)
        assert len(failures) == 1
        assert failures[0].kind is FailureKind.SCOPE_MISMATCH
        assert "SingletonNeedsRequest" in failures[0].message
        assert "RequestDep" in failures[0].message
        assert failures[0].component is SingletonNeedsRequest
        assert failures[0].parameter == "dep"

    def test_request_scoped_depending_on_request_scoped_passes(self) -> None:
        """A request-scoped component can depend on another request-scoped one."""
        registrations = _make_registrations(
            ComponentNode(
                impl=RequestDep,
                provides=RequestDep,
                scope=Scope.REQUEST,
            ),
            ComponentNode(
                impl=RequestNeedsRequest,
                provides=RequestNeedsRequest,
                scope=Scope.REQUEST,
            ),
        )
        assert build_graph(registrations) == []

    def test_transient_depending_on_request_scoped_passes(self) -> None:
        """A transient component can depend on a request-scoped one."""
        registrations = _make_registrations(
            ComponentNode(
                impl=RequestDep,
                provides=RequestDep,
                scope=Scope.REQUEST,
            ),
            ComponentNode(
                impl=TransientNeedsRequest,
                provides=TransientNeedsRequest,
                scope=Scope.TRANSIENT,
            ),
        )
        assert build_graph(registrations) == []


class SingletonDep:
    pass


class TransientDep:
    pass


class AutoNeedsSingleton:
    def __init__(self, dep: SingletonDep) -> None:
        self.dep = dep


class AutoNeedsRequest:
    def __init__(self, dep: RequestDep) -> None:
        self.dep = dep


class AutoNeedsTransient:
    def __init__(self, dep: TransientDep) -> None:
        self.dep = dep


class AutoNeedsMixed:
    def __init__(self, s: SingletonDep, r: RequestDep, t: TransientDep) -> None:
        self.s = s
        self.r = r
        self.t = t


class AutoNeedsAutoRequest:
    def __init__(self, dep: AutoNeedsRequest) -> None:
        self.dep = dep


class AutoNeedsAutoSingleton:
    def __init__(self, dep: AutoNeedsSingleton) -> None:
        self.dep = dep


class AutoCycleA:
    def __init__(self, dep: AutoCycleB) -> None:
        self.dep = dep


class AutoCycleB:
    def __init__(self, dep: AutoCycleA) -> None:
        self.dep = dep


class AutoNoDeps:
    pass


class TestAutoScope:
    def test_auto_with_no_deps_resolves_to_singleton(self) -> None:
        registrations = _make_registrations(
            ComponentNode(impl=AutoNoDeps, provides=AutoNoDeps, scope=Scope.AUTO),
        )
        assert build_graph(registrations) == []
        assert registrations[(AutoNoDeps, None)].scope is Scope.SINGLETON

    def test_auto_with_singleton_dep_resolves_to_singleton(self) -> None:
        registrations = _make_registrations(
            ComponentNode(impl=SingletonDep, provides=SingletonDep),
            ComponentNode(
                impl=AutoNeedsSingleton,
                provides=AutoNeedsSingleton,
                scope=Scope.AUTO,
            ),
        )
        assert build_graph(registrations) == []
        assert registrations[(AutoNeedsSingleton, None)].scope is Scope.SINGLETON

    def test_auto_with_request_dep_resolves_to_request(self) -> None:
        registrations = _make_registrations(
            ComponentNode(
                impl=RequestDep,
                provides=RequestDep,
                scope=Scope.REQUEST,
            ),
            ComponentNode(
                impl=AutoNeedsRequest,
                provides=AutoNeedsRequest,
                scope=Scope.AUTO,
            ),
        )
        assert build_graph(registrations) == []
        assert registrations[(AutoNeedsRequest, None)].scope is Scope.REQUEST

    def test_auto_with_transient_dep_resolves_to_singleton(self) -> None:
        registrations = _make_registrations(
            ComponentNode(
                impl=TransientDep,
                provides=TransientDep,
                scope=Scope.TRANSIENT,
            ),
            ComponentNode(
                impl=AutoNeedsTransient,
                provides=AutoNeedsTransient,
                scope=Scope.AUTO,
            ),
        )
        assert build_graph(registrations) == []
        assert registrations[(AutoNeedsTransient, None)].scope is Scope.SINGLETON

    def test_auto_with_mixed_deps_picks_request(self) -> None:
        registrations = _make_registrations(
            ComponentNode(impl=SingletonDep, provides=SingletonDep),
            ComponentNode(
                impl=RequestDep,
                provides=RequestDep,
                scope=Scope.REQUEST,
            ),
            ComponentNode(
                impl=TransientDep,
                provides=TransientDep,
                scope=Scope.TRANSIENT,
            ),
            ComponentNode(
                impl=AutoNeedsMixed,
                provides=AutoNeedsMixed,
                scope=Scope.AUTO,
            ),
        )
        assert build_graph(registrations) == []
        assert registrations[(AutoNeedsMixed, None)].scope is Scope.REQUEST

    def test_transitive_auto_chain_propagates_request(self) -> None:
        registrations = _make_registrations(
            ComponentNode(
                impl=RequestDep,
                provides=RequestDep,
                scope=Scope.REQUEST,
            ),
            ComponentNode(
                impl=AutoNeedsRequest,
                provides=AutoNeedsRequest,
                scope=Scope.AUTO,
            ),
            ComponentNode(
                impl=AutoNeedsAutoRequest,
                provides=AutoNeedsAutoRequest,
                scope=Scope.AUTO,
            ),
        )
        assert build_graph(registrations) == []
        assert registrations[(AutoNeedsRequest, None)].scope is Scope.REQUEST
        assert registrations[(AutoNeedsAutoRequest, None)].scope is Scope.REQUEST

    def test_transitive_auto_chain_all_singletons(self) -> None:
        registrations = _make_registrations(
            ComponentNode(impl=SingletonDep, provides=SingletonDep),
            ComponentNode(
                impl=AutoNeedsSingleton,
                provides=AutoNeedsSingleton,
                scope=Scope.AUTO,
            ),
            ComponentNode(
                impl=AutoNeedsAutoSingleton,
                provides=AutoNeedsAutoSingleton,
                scope=Scope.AUTO,
            ),
        )
        assert build_graph(registrations) == []
        assert registrations[(AutoNeedsSingleton, None)].scope is Scope.SINGLETON
        assert registrations[(AutoNeedsAutoSingleton, None)].scope is Scope.SINGLETON

    def test_auto_cycle_produces_failure(self) -> None:
        registrations = _make_registrations(
            ComponentNode(
                impl=AutoCycleA,
                provides=AutoCycleA,
                scope=Scope.AUTO,
            ),
            ComponentNode(
                impl=AutoCycleB,
                provides=AutoCycleB,
                scope=Scope.AUTO,
            ),
        )
        failures = build_graph(registrations)
        auto_failures = [f for f in failures if f.kind is FailureKind.AUTO_CYCLE]
        assert len(auto_failures) == 1
        assert "AutoCycleA" in auto_failures[0].message
        assert "AutoCycleB" in auto_failures[0].message

    def test_explicit_scope_not_overridden(self) -> None:
        """Explicit SINGLETON depending on REQUEST still fails (not auto-resolved)."""
        registrations = _make_registrations(
            ComponentNode(
                impl=RequestDep,
                provides=RequestDep,
                scope=Scope.REQUEST,
            ),
            ComponentNode(
                impl=SingletonNeedsRequest,
                provides=SingletonNeedsRequest,
                scope=Scope.SINGLETON,
            ),
        )
        failures = build_graph(registrations)
        assert any(f.kind is FailureKind.SCOPE_MISMATCH for f in failures)

    def test_auto_factory(self) -> None:
        def create_service(dep: RequestDep) -> AutoNeedsRequest:
            return AutoNeedsRequest(dep)

        registrations = _make_registrations(
            ComponentNode(
                impl=RequestDep,
                provides=RequestDep,
                scope=Scope.REQUEST,
            ),
            ComponentNode(
                impl=AutoNeedsRequest,
                provides=AutoNeedsRequest,
                scope=Scope.AUTO,
                factory=create_service,
            ),
        )
        assert build_graph(registrations) == []
        assert registrations[(AutoNeedsRequest, None)].scope is Scope.REQUEST


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
