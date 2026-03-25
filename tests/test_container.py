import types
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Annotated, Protocol

import pytest

from uncoiled import (
    Container,
    DependencyResolutionError,
    EnvVar,
    Qualifier,
    Scope,
    component,
)


class Repository:
    pass


class UserService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo


class TestContainerRegistration:
    def test_register_and_get(self) -> None:
        c = Container()
        c.register(Repository)
        assert isinstance(c.get(Repository), Repository)

    def test_register_with_qualifier(self) -> None:
        c = Container()
        c.register(Repository, qualifier="primary")
        assert isinstance(c.get(Repository, qualifier="primary"), Repository)

    def test_register_instance(self) -> None:
        repo = Repository()
        c = Container()
        c.register_instance(repo)
        assert c.get(Repository) is repo

    def test_register_factory(self) -> None:
        c = Container()
        c.register_factory(Repository, return_type=Repository)
        assert isinstance(c.get(Repository), Repository)

    def test_register_factory_resolves_dependencies(self) -> None:
        def make_service(repo: Repository) -> UserService:
            return UserService(repo)

        c = Container()
        c.register(Repository)
        c.register_factory(make_service, return_type=UserService)
        svc = c.get(UserService)
        assert isinstance(svc, UserService)
        assert isinstance(svc.repo, Repository)

    def test_register_factory_validates_dependencies(self) -> None:
        def make_service(repo: Repository) -> UserService:
            return UserService(repo)

        c = Container()
        c.register_factory(make_service, return_type=UserService)
        with pytest.raises(DependencyResolutionError):
            c.validate()

    def test_duplicate_register_raises(self) -> None:
        c = Container()
        c.register(Repository)
        with pytest.raises(ValueError, match="already exists"):
            c.register(Repository)

    def test_duplicate_register_with_replace(self) -> None:
        class MockRepo(Repository):
            pass

        c = Container()
        c.register(Repository)
        c.register(MockRepo, provides=Repository, replace=True)
        assert isinstance(c.get(Repository), MockRepo)

    def test_duplicate_register_instance_raises(self) -> None:
        c = Container()
        c.register_instance(Repository())
        with pytest.raises(ValueError, match="already exists"):
            c.register_instance(Repository())

    def test_duplicate_register_factory_raises(self) -> None:
        c = Container()
        c.register_factory(Repository, return_type=Repository)
        with pytest.raises(ValueError, match="already exists"):
            c.register_factory(Repository, return_type=Repository)

    def test_register_incompatible_provides_raises(self) -> None:
        c = Container()
        with pytest.raises(TypeError, match="not a subclass"):
            c.register(str, provides=int)

    def test_register_compatible_provides_passes(self) -> None:
        class Sub(Repository):
            pass

        c = Container()
        c.register(Sub, provides=Repository)
        assert isinstance(c.get(Repository), Sub)

    def test_register_provides_protocol_skips_check(self) -> None:
        class MyProtocol(Protocol):
            def do_thing(self) -> None: ...

        class Impl:
            def do_thing(self) -> None: ...

        c = Container()
        c.register(Impl, provides=MyProtocol)

    def test_register_provides_abc_validates(self) -> None:
        class Base(ABC):
            @abstractmethod
            def do_thing(self) -> None: ...

        class Impl(Base):
            def do_thing(self) -> None: ...

        c = Container()
        c.register(Impl, provides=Base)
        assert isinstance(c.get(Base), Impl)

    def test_register_provides_abc_rejects_incompatible(self) -> None:
        class Base(ABC):
            @abstractmethod
            def do_thing(self) -> None: ...

        c = Container()
        with pytest.raises(TypeError, match="not a subclass"):
            c.register(str, provides=Base)

    def test_register_rejects_invalid_init_method(self) -> None:
        c = Container()
        with pytest.raises(ValueError, match=r"init_method.*nonexistent.*Repository"):
            c.register(Repository, init_method="nonexistent")

    def test_register_rejects_invalid_destroy_method(self) -> None:
        c = Container()
        with pytest.raises(ValueError, match=r"destroy_method.*nonexistent"):
            c.register(Repository, destroy_method="nonexistent")


class TestContainerResolution:
    def test_singleton_scope(self) -> None:
        c = Container()
        c.register(Repository)
        first = c.get(Repository)
        second = c.get(Repository)
        assert first is second

    def test_transient_scope(self) -> None:
        c = Container()
        c.register(Repository, scope=Scope.TRANSIENT)
        first = c.get(Repository)
        second = c.get(Repository)
        assert first is not second

    def test_dependency_injection(self) -> None:
        c = Container()
        c.register(Repository)
        c.register(UserService)
        svc = c.get(UserService)
        assert isinstance(svc.repo, Repository)

    def test_optional_dependency_none(self) -> None:
        class OptService:
            def __init__(self, repo: Repository | None = None) -> None:
                self.repo = repo

        c = Container()
        c.register(OptService)
        assert c.get(OptService).repo is None

    def test_optional_dependency_present(self) -> None:
        class OptService:
            def __init__(self, repo: Repository | None = None) -> None:
                self.repo = repo

        c = Container()
        c.register(Repository)
        c.register(OptService)
        assert isinstance(c.get(OptService).repo, Repository)

    def test_optional_with_default_preserves_default(self) -> None:
        sentinel = object()

        class OptService:
            def __init__(self, repo: Repository | None = sentinel) -> None:  # ty: ignore[invalid-parameter-default]
                self.repo = repo

        c = Container()
        c.register(OptService)
        assert c.get(OptService).repo is sentinel

    def test_non_optional_with_default_preserves_default(self) -> None:
        default_repo = Repository()

        class OptService:
            def __init__(self, repo: Repository = default_repo) -> None:
                self.repo = repo

        c = Container()
        c.register(OptService)
        assert c.get(OptService).repo is default_repo

    def test_list_dependency(self) -> None:
        class RepoA(Repository):
            pass

        class RepoB(Repository):
            pass

        class MultiService:
            def __init__(self, repos: list[Repository]) -> None:
                self.repos = repos

        c = Container()
        c.register(RepoA, provides=Repository, qualifier="a")
        c.register(RepoB, provides=Repository, qualifier="b")
        c.register(MultiService)
        svc = c.get(MultiService)
        expected_count = 2
        assert len(svc.repos) == expected_count

    def test_missing_dependency_raises(self) -> None:
        c = Container()
        with pytest.raises(LookupError, match="UserService"):
            c.get(UserService)

    def test_get_all(self) -> None:
        class RepoA(Repository):
            pass

        class RepoB(Repository):
            pass

        c = Container()
        c.register(RepoA, provides=Repository, qualifier="a")
        c.register(RepoB, provides=Repository, qualifier="b")
        results = c.get_all(Repository)
        expected_count = 2
        assert len(results) == expected_count

    def test_get_all_with_qualifier(self) -> None:
        class RepoA(Repository):
            pass

        class RepoB(Repository):
            pass

        c = Container()
        c.register(RepoA, provides=Repository, qualifier="a")
        c.register(RepoB, provides=Repository, qualifier="b")
        results = c.get_all(Repository, qualifier="a")
        assert len(results) == 1
        assert isinstance(results[0], RepoA)

    def test_list_dependency_with_qualifier(self) -> None:
        class RepoA(Repository):
            pass

        class RepoB(Repository):
            pass

        class FilteredService:
            def __init__(
                self,
                repos: Annotated[list[Repository], Qualifier("a")],
            ) -> None:
                self.repos = repos

        c = Container()
        c.register(RepoA, provides=Repository, qualifier="a")
        c.register(RepoB, provides=Repository, qualifier="b")
        c.register(FilteredService)
        svc = c.get(FilteredService)
        assert len(svc.repos) == 1
        assert isinstance(svc.repos[0], RepoA)

    def test_dataclass_injection(self) -> None:
        """Dataclass fields are injected without a manual __init__."""

        @dataclass
        class Service:
            repo: Repository

        c = Container()
        c.register(Repository)
        c.register(Service)
        svc = c.get(Service)
        assert isinstance(svc.repo, Repository)

    def test_get_all_finds_subclass_registered_as_itself(self) -> None:
        """get_all should find subclasses even when registered as their own type."""

        class SpecialRepo(Repository):
            pass

        c = Container()
        c.register(SpecialRepo)  # registered as SpecialRepo, not provides=Repository
        results = c.get_all(Repository)
        assert len(results) == 1
        assert isinstance(results[0], SpecialRepo)


class TestEnvVar:
    def test_injects_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_DB_URL", "postgres://localhost/test")

        class Service:
            def __init__(
                self,
                db_url: Annotated[str, EnvVar("TEST_DB_URL")],
            ) -> None:
                self.db_url = db_url

        c = Container()
        c.register(Service)
        assert c.get(Service).db_url == "postgres://localhost/test"

    def test_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TEST_DB_URL", raising=False)

        class Service:
            def __init__(
                self,
                db_url: Annotated[str, EnvVar("TEST_DB_URL")] = ":memory:",
            ) -> None:
                self.db_url = db_url

        c = Container()
        c.register(Service)
        assert c.get(Service).db_url == ":memory:"

    def test_raises_when_missing_no_default(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("TEST_REQUIRED", raising=False)

        class Service:
            def __init__(
                self,
                val: Annotated[str, EnvVar("TEST_REQUIRED")],
            ) -> None:
                self.val = val

        c = Container()
        c.register(Service)
        with pytest.raises(LookupError, match="TEST_REQUIRED"):
            c.get(Service)

    def test_coerces_int(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_PORT", "8080")

        class Service:
            def __init__(
                self,
                port: Annotated[int, EnvVar("TEST_PORT")],
            ) -> None:
                self.port = port

        c = Container()
        c.register(Service)
        assert c.get(Service).port == 8080

    def test_coerces_bool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_DEBUG", "true")

        class Service:
            def __init__(
                self,
                debug: Annotated[bool, EnvVar("TEST_DEBUG")],
            ) -> None:
                self.debug = debug

        c = Container()
        c.register(Service)
        assert c.get(Service).debug is True

    def test_graph_validation_passes(self) -> None:
        class Service:
            def __init__(
                self,
                db_url: Annotated[str, EnvVar("DB_URL")] = ":memory:",
            ) -> None:
                self.db_url = db_url

        c = Container()
        c.register(Service)
        c.validate()  # should not raise


class TestContainerValidation:
    def test_validate_raises_on_missing(self) -> None:
        c = Container()
        c.register(UserService)
        with pytest.raises(DependencyResolutionError):
            c.validate()

    def test_validate_passes_valid(self) -> None:
        c = Container()
        c.register(Repository)
        c.register(UserService)
        c.validate()


class TestContainerLifecycle:
    def test_start_instantiates_singletons(self) -> None:
        c = Container()
        c.register(Repository)
        c.start()
        assert c.get(Repository) is not None

    def test_close_calls_destroy(self) -> None:
        class Resource:
            closed = False

            def close(self) -> None:
                self.closed = True

        c = Container()
        c.register(Resource)
        c.start()
        res = c.get(Resource)
        c.close()
        assert res.closed

    def test_init_method(self) -> None:
        class Service:
            started = False

            def start(self) -> None:
                self.started = True

        c = Container()
        c.register(Service, init_method="start")
        svc = c.get(Service)
        assert svc.started

    def test_context_manager(self) -> None:
        c = Container()
        c.register(Repository)
        with c:
            repo = c.get(Repository)
            assert isinstance(repo, Repository)

    @pytest.mark.anyio
    async def test_async_context_manager(self) -> None:
        c = Container()
        c.register(Repository)
        async with c:
            repo = c.get(Repository)
            assert isinstance(repo, Repository)

    @pytest.mark.anyio
    async def test_astart_calls_async_init(self) -> None:
        class Service:
            started = False

            async def start(self) -> None:
                self.started = True

        c = Container()
        c.register(Service, init_method="start")
        await c.astart()
        assert c.get(Service).started

    @pytest.mark.anyio
    async def test_aclose_calls_async_destroy(self) -> None:
        class Resource:
            closed = False

            async def shutdown(self) -> None:
                self.closed = True

        c = Container()
        c.register(Resource, destroy_method="shutdown")
        await c.astart()
        res = c.get(Resource)
        await c.aclose()
        assert res.closed

    @pytest.mark.anyio
    async def test_aclose_calls_async_disposable(self) -> None:
        class Resource:
            closed = False

            async def aclose(self) -> None:
                self.closed = True

        c = Container()
        c.register(Resource)
        await c.astart()
        res = c.get(Resource)
        await c.aclose()
        assert res.closed

    @pytest.mark.anyio
    async def test_aclose_continues_on_error(self) -> None:
        class FailResource:
            async def aclose(self) -> None:
                msg = "fail"
                raise RuntimeError(msg)

        class GoodResource:
            closed = False

            async def aclose(self) -> None:
                self.closed = True

        c = Container()
        c.register(GoodResource)
        c.register(FailResource)
        await c.astart()
        good = c.get(GoodResource)
        with pytest.raises(ExceptionGroup):
            await c.aclose()
        assert good.closed

    def test_register_instance_destroy_method(self) -> None:
        class Resource:
            closed = False

            def shutdown(self) -> None:
                self.closed = True

        res = Resource()
        c = Container()
        c.register_instance(res, destroy_method="shutdown")
        c.close()
        assert res.closed

    def test_register_factory_init_method(self) -> None:
        class Service:
            started = False

            def start(self) -> None:
                self.started = True

        c = Container()
        c.register_factory(Service, return_type=Service, init_method="start")
        svc = c.get(Service)
        assert svc.started

    def test_register_factory_destroy_method(self) -> None:
        class Resource:
            closed = False

            def shutdown(self) -> None:
                self.closed = True

        c = Container()
        c.register_factory(Resource, return_type=Resource, destroy_method="shutdown")
        c.start()
        res = c.get(Resource)
        c.close()
        assert res.closed

    def test_qualified_init_methods_are_independent(self) -> None:
        class ServiceA(Repository):
            started = False

            def boot(self) -> None:
                self.started = True

        class ServiceB(Repository):
            started = False

            def setup(self) -> None:
                self.started = True

        c = Container()
        c.register(
            ServiceA,
            provides=Repository,
            qualifier="a",
            init_method="boot",
        )
        c.register(
            ServiceB,
            provides=Repository,
            qualifier="b",
            init_method="setup",
        )
        c.start()
        a = c.get(Repository, qualifier="a")
        b = c.get(Repository, qualifier="b")
        assert a.started  # ty: ignore[unresolved-attribute]
        assert b.started  # ty: ignore[unresolved-attribute]

    def test_qualified_destroy_methods_are_independent(self) -> None:
        class ResourceA(Repository):
            closed = False

            def teardown(self) -> None:
                self.closed = True

        class ResourceB(Repository):
            closed = False

            def cleanup(self) -> None:
                self.closed = True

        c = Container()
        c.register(
            ResourceA,
            provides=Repository,
            qualifier="a",
            destroy_method="teardown",
        )
        c.register(
            ResourceB,
            provides=Repository,
            qualifier="b",
            destroy_method="cleanup",
        )
        c.start()
        a = c.get(Repository, qualifier="a")
        b = c.get(Repository, qualifier="b")
        c.close()
        assert a.closed  # ty: ignore[unresolved-attribute]
        assert b.closed  # ty: ignore[unresolved-attribute]


class TestSingletonQualifierIsolation:
    def test_different_qualifiers_return_different_instances(self) -> None:
        class RepoA(Repository):
            pass

        class RepoB(Repository):
            pass

        c = Container()
        c.register(RepoA, provides=Repository, qualifier="a")
        c.register(RepoB, provides=Repository, qualifier="b")

        a = c.get(Repository, qualifier="a")
        b = c.get(Repository, qualifier="b")
        assert isinstance(a, RepoA)
        assert isinstance(b, RepoB)

    def test_register_instance_with_qualifier(self) -> None:
        repo_a = Repository()
        repo_b = Repository()
        c = Container()
        c.register_instance(repo_a, qualifier="a")
        c.register_instance(repo_b, qualifier="b")
        assert c.get(Repository, qualifier="a") is repo_a
        assert c.get(Repository, qualifier="b") is repo_b


class TestCloseErrorHandling:
    def test_close_continues_on_destroy_error(self) -> None:
        class FailResource:
            def close(self) -> None:
                msg = "fail"
                raise RuntimeError(msg)

        class GoodResource:
            closed = False

            def close(self) -> None:
                self.closed = True

        c = Container()
        c.register(GoodResource, destroy_method="close")
        c.register(FailResource, destroy_method="close")
        c.start()
        good = c.get(GoodResource)
        with pytest.raises(ExceptionGroup):
            c.close()
        assert good.closed

    def test_close_aggregates_multiple_errors(self) -> None:
        class FailA:
            def close(self) -> None:
                msg = "a"
                raise RuntimeError(msg)

        class FailB:
            def close(self) -> None:
                msg = "b"
                raise RuntimeError(msg)

        c = Container()
        c.register(FailA, destroy_method="close")
        c.register(FailB, destroy_method="close")
        c.start()
        expected_count = 2
        with pytest.raises(ExceptionGroup) as exc_info:
            c.close()
        assert len(exc_info.value.exceptions) == expected_count


class TestTransientMemoryLeak:
    def test_transient_without_destroy_not_tracked(self) -> None:
        c = Container()
        c.register(Repository, scope=Scope.TRANSIENT)
        resolve_count = 10
        for _ in range(resolve_count):
            c.get(Repository)
        assert len(c._instances) == 0  # noqa: SLF001

    def test_transient_with_destroy_hook_tracked(self) -> None:
        class Resource:
            def close(self) -> None:
                pass

        c = Container()
        c.register(Resource, scope=Scope.TRANSIENT, destroy_method="close")
        resolve_count = 3
        for _ in range(resolve_count):
            c.get(Resource)
        assert len(c._instances) == resolve_count  # noqa: SLF001


class TestContainerOverride:
    def test_override_replaces_with_class(self) -> None:
        class MockRepo(Repository):
            pass

        c = Container()
        c.register(Repository)
        c.start()
        original = c.get(Repository)
        with c.override(Repository, MockRepo):
            assert isinstance(c.get(Repository), MockRepo)
        assert c.get(Repository) is original

    def test_override_replaces_with_instance(self) -> None:
        mock = Repository()
        c = Container()
        c.register(Repository)
        c.start()
        with c.override(Repository, mock):
            assert c.get(Repository) is mock

    def test_override_restores_cached_singleton(self) -> None:
        c = Container()
        c.register(Repository)
        c.start()
        original = c.get(Repository)
        with c.override(Repository, Repository):
            pass
        assert c.get(Repository) is original

    def test_override_nonexistent_key(self) -> None:
        c = Container()
        with c.override(Repository, Repository):
            assert isinstance(c.get(Repository), Repository)
        with pytest.raises(LookupError):
            c.get(Repository)

    def test_override_with_qualifier(self) -> None:
        class RepoA(Repository):
            pass

        class RepoB(Repository):
            pass

        class MockRepo(Repository):
            pass

        c = Container()
        c.register(RepoA, provides=Repository, qualifier="a")
        c.register(RepoB, provides=Repository, qualifier="b")
        c.start()
        with c.override(Repository, MockRepo, qualifier="a"):
            assert isinstance(c.get(Repository, qualifier="a"), MockRepo)
            assert isinstance(c.get(Repository, qualifier="b"), RepoB)

    def test_nested_overrides(self) -> None:
        class MockA(Repository):
            pass

        class MockB(Repository):
            pass

        c = Container()
        c.register(Repository)
        c.start()
        original = c.get(Repository)
        with c.override(Repository, MockA):
            assert isinstance(c.get(Repository), MockA)
            with c.override(Repository, MockB):
                assert isinstance(c.get(Repository), MockB)
            assert isinstance(c.get(Repository), MockA)
        assert c.get(Repository) is original


class TestContainerFork:
    def test_fork_shares_registrations(self) -> None:
        c = Container()
        c.register(Repository)
        child = c.fork()
        assert isinstance(child.get(Repository), Repository)

    def test_fork_independent_singleton_cache(self) -> None:
        c = Container()
        c.register(Repository)
        c.start()
        child = c.fork()
        assert c.get(Repository) is not child.get(Repository)

    def test_fork_does_not_affect_parent(self) -> None:
        class Extra:
            pass

        c = Container()
        c.register(Repository)
        child = c.fork()
        child.register(Extra)
        assert isinstance(child.get(Extra), Extra)
        with pytest.raises(LookupError):
            c.get(Extra)

    def test_fork_inherits_lifecycle_hooks(self) -> None:
        class Service:
            started = False

            def start(self) -> None:
                self.started = True

        c = Container()
        c.register(Service, init_method="start")
        child = c.fork()
        svc = child.get(Service)
        assert svc.started

    def test_fork_child_can_override_registration(self) -> None:
        class MockRepo(Repository):
            pass

        c = Container()
        c.register(Repository)
        child = c.fork()
        child.register(MockRepo, provides=Repository, replace=True)
        assert isinstance(child.get(Repository), MockRepo)
        assert not isinstance(c.get(Repository), MockRepo)


class _TenantId(str):
    __slots__ = ()


class TestRequestValue:
    def test_register_and_provide_round_trip(self) -> None:
        c = Container()
        c.register_request_value(_TenantId)
        with c.request_context():
            c.provide_request_value(_TenantId, _TenantId("acme"))
            assert c.get(_TenantId) == "acme"

    def test_error_when_value_not_provided(self) -> None:
        c = Container()
        c.register_request_value(_TenantId)
        with (
            c.request_context(),
            pytest.raises(
                LookupError,
                match="not provided",
            ),
        ):
            c.get(_TenantId)

    def test_provide_unregistered_raises(self) -> None:
        c = Container()
        with (
            c.request_context(),
            pytest.raises(
                LookupError,
                match="No request value registered",
            ),
        ):
            c.provide_request_value(_TenantId, _TenantId("x"))

    def test_qualified_request_value(self) -> None:
        c = Container()
        c.register_request_value(str, qualifier="correlation_id")
        with c.request_context():
            c.provide_request_value(
                str,
                "abc-123",
                qualifier="correlation_id",
            )
            result = c.get(str, qualifier="correlation_id")
            assert result == "abc-123"

    def test_injected_into_request_scoped_component(self) -> None:
        class TenantRepo:
            def __init__(self, tenant: _TenantId) -> None:
                self.tenant = tenant

        c = Container()
        c.register_request_value(_TenantId)
        c.register(TenantRepo, scope=Scope.REQUEST)
        with c.request_context():
            c.provide_request_value(
                _TenantId,
                _TenantId("acme"),
            )
            repo = c.get(TenantRepo)
            assert repo.tenant == "acme"

    def test_graph_validation_passes(self) -> None:
        class TenantRepo:
            def __init__(self, tenant: _TenantId) -> None:
                self.tenant = tenant

        c = Container()
        c.register_request_value(_TenantId)
        c.register(TenantRepo, scope=Scope.REQUEST)
        c.validate()  # should not raise

    def test_different_values_across_contexts(self) -> None:
        c = Container()
        c.register_request_value(_TenantId)
        with c.request_context():
            c.provide_request_value(
                _TenantId,
                _TenantId("acme"),
            )
            assert c.get(_TenantId) == "acme"
        with c.request_context():
            c.provide_request_value(
                _TenantId,
                _TenantId("globex"),
            )
            assert c.get(_TenantId) == "globex"


class TestRequestScope:
    def test_same_instance_within_context(self) -> None:
        c = Container()
        c.register(Repository, scope=Scope.REQUEST)
        with c.request_context():
            first = c.get(Repository)
            second = c.get(Repository)
            assert first is second

    def test_different_instances_across_contexts(self) -> None:
        c = Container()
        c.register(Repository, scope=Scope.REQUEST)
        with c.request_context():
            first = c.get(Repository)
        with c.request_context():
            second = c.get(Repository)
        assert first is not second

    def test_resolve_outside_context_raises(self) -> None:
        c = Container()
        c.register(Repository, scope=Scope.REQUEST)
        with pytest.raises(LookupError, match="request context"):
            c.get(Repository)


class TestContainerScan:
    def test_scan_finds_decorated_classes(self) -> None:
        @component
        class ScanService:
            pass

        mod = types.ModuleType("test_scan_mod")
        mod.ScanService = ScanService  # ty: ignore[unresolved-attribute]

        c = Container()
        c.scan(mod)
        assert isinstance(c.get(ScanService), ScanService)

    def test_scan_honours_provides(self) -> None:
        class Base:
            pass

        @component(provides=Base)
        class Impl(Base):
            pass

        mod = types.ModuleType("test_scan_provides")
        mod.Impl = Impl  # ty: ignore[unresolved-attribute]

        c = Container()
        c.scan(mod)
        assert isinstance(c.get(Base), Impl)

    def test_scan_walks_subpackages(self, tmp_path: pytest.TempPathFactory) -> None:
        """scan() should discover components in submodules of a package."""
        import sys  # noqa: PLC0415

        # Create a real package on disk so pkgutil.walk_packages works
        pkg_dir = tmp_path / "test_scan_pkg"  # ty: ignore[unsupported-operator]
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        (pkg_dir / "sub.py").write_text(
            "from uncoiled import component\n\n"
            "@component\n"
            "class SubComponent:\n"
            "    pass\n",
        )

        sys.path.insert(0, str(tmp_path))
        try:
            c = Container()
            c.scan("test_scan_pkg")
            # Import the class to use as a lookup key
            from test_scan_pkg.sub import SubComponent  # ty: ignore[unresolved-import]  # noqa: PLC0415, I001

            assert isinstance(c.get(SubComponent), SubComponent)
        finally:
            sys.path.remove(str(tmp_path))
            sys.modules.pop("test_scan_pkg", None)
            sys.modules.pop("test_scan_pkg.sub", None)


class TestContainerLifecycleState:
    def test_started_false_before_start(self) -> None:
        c = Container()
        c.register(Repository)
        assert c._started is False  # noqa: SLF001

    def test_started_true_after_start(self) -> None:
        c = Container()
        c.register(Repository)
        c.start()
        assert c._started is True  # noqa: SLF001

    def test_started_false_after_close(self) -> None:
        c = Container()
        c.register(Repository)
        c.start()
        c.close()
        assert c._started is False  # noqa: SLF001

    @pytest.mark.anyio
    async def test_started_true_after_astart(self) -> None:
        c = Container()
        c.register(Repository)
        await c.astart()
        assert c._started is True  # noqa: SLF001

    @pytest.mark.anyio
    async def test_started_false_after_aclose(self) -> None:
        c = Container()
        c.register(Repository)
        await c.astart()
        await c.aclose()
        assert c._started is False  # noqa: SLF001

    def test_start_calls_init_hooks_for_singletons(self) -> None:
        class Service:
            started = False

            def initialize(self) -> None:
                self.started = True

        c = Container()
        c.register(Service, init_method="initialize")
        c.start()
        assert c.get(Service).started

    def test_close_clears_scope_caches(self) -> None:
        c = Container()
        c.register(Repository)
        c.start()
        repo = c.get(Repository)
        assert repo is not None
        c.close()
        # After close, the singleton cache should be cleared
        singleton = c._scopes[Scope.SINGLETON]  # noqa: SLF001
        assert singleton.get(Repository) is None

    @pytest.mark.anyio
    async def test_aclose_clears_scope_caches(self) -> None:
        c = Container()
        c.register(Repository)
        await c.astart()
        c.get(Repository)
        await c.aclose()
        singleton = c._scopes[Scope.SINGLETON]  # noqa: SLF001
        assert singleton.get(Repository) is None

    @pytest.mark.anyio
    async def test_astart_calls_init_hooks_for_singletons(self) -> None:
        class Service:
            started = False

            async def initialize(self) -> None:
                self.started = True

        c = Container()
        c.register(Service, init_method="initialize")
        await c.astart()
        assert c.get(Service).started


class TestGetAllQualifierFiltering:
    def test_get_all_with_qualifier_skips_non_matching(self) -> None:
        class RepoA(Repository):
            pass

        class RepoB(Repository):
            pass

        class RepoC(Repository):
            pass

        c = Container()
        c.register(RepoA, provides=Repository, qualifier="a")
        c.register(RepoB, provides=Repository, qualifier="b")
        c.register(RepoC, provides=Repository, qualifier="c")
        results = c.get_all(Repository, qualifier="b")
        assert len(results) == 1
        assert isinstance(results[0], RepoB)

    def test_get_all_without_qualifier_returns_all(self) -> None:
        class RepoA(Repository):
            pass

        class RepoB(Repository):
            pass

        c = Container()
        c.register(RepoA, provides=Repository, qualifier="a")
        c.register(RepoB, provides=Repository, qualifier="b")
        expected = 2
        assert len(c.get_all(Repository)) == expected

    def test_resolve_missing_with_qualifier_includes_qualifier_in_error(self) -> None:
        c = Container()
        with pytest.raises(LookupError, match="primary"):
            c.get(Repository, qualifier="primary")

    @pytest.mark.anyio
    async def test_aresolve_caches_singleton(self) -> None:
        """Async resolution should cache singletons, returning same instance."""
        c = Container()
        c.register(Repository)
        await c.astart()
        first = c.get(Repository)
        second = c.get(Repository)
        assert first is second

    @pytest.mark.anyio
    async def test_aresolve_missing_with_qualifier_includes_qualifier(self) -> None:
        c = Container()
        with pytest.raises(LookupError, match="primary"):
            await c._aresolve(Repository, "primary")  # noqa: SLF001

    @pytest.mark.anyio
    async def test_astart_instantiates_qualified_singletons(self) -> None:
        class RepoA(Repository):
            pass

        class RepoB(Repository):
            pass

        c = Container()
        c.register(RepoA, provides=Repository, qualifier="a")
        c.register(RepoB, provides=Repository, qualifier="b")
        await c.astart()
        a = c.get(Repository, qualifier="a")
        b = c.get(Repository, qualifier="b")
        assert isinstance(a, RepoA)
        assert isinstance(b, RepoB)

    @pytest.mark.anyio
    async def test_aresolve_singleton_returns_same_instance(self) -> None:
        """Calling _aresolve twice should return the cached singleton."""
        c = Container()
        c.register(Repository)
        c.validate()
        first = await c._aresolve(Repository)  # noqa: SLF001
        second = await c._aresolve(Repository)  # noqa: SLF001
        assert first is second


class TestVisualise:
    def test_empty_container(self) -> None:
        c = Container()
        result = c.visualise()
        assert result.startswith("graph TD")

    def test_single_component(self) -> None:
        c = Container()
        c.register(Repository)
        result = c.visualise()
        assert "Repository" in result

    def test_dependency_edge(self) -> None:
        c = Container()
        c.register(Repository)
        c.register(UserService)
        result = c.visualise()
        assert "Repository" in result
        assert "UserService" in result
        assert "-->" in result

    def test_scope_label_uses_quoted_br(self) -> None:
        c = Container()
        c.register(Repository, scope=Scope.TRANSIENT)
        result = c.visualise()
        assert '"Repository<br/>(transient)"' in result

    def test_qualifier_label_uses_quoted_br(self) -> None:
        class RepoA(Repository):
            pass

        c = Container()
        c.register(RepoA, provides=Repository, qualifier="primary")
        result = c.visualise()
        assert '"RepoA<br/>(as Repository, qualifier=primary)"' in result

    def test_provides_label_uses_quoted_br(self) -> None:
        class Impl(Repository):
            pass

        c = Container()
        c.register(Impl, provides=Repository)
        result = c.visualise()
        assert '"Impl<br/>(as Repository)"' in result

    def test_singleton_label_has_no_annotation(self) -> None:
        c = Container()
        c.register(Repository)
        result = c.visualise()
        assert "Repository[Repository]" in result

    def test_envvar_shown(self) -> None:
        class Service:
            def __init__(
                self,
                url: Annotated[str, EnvVar("DB_URL")] = ":memory:",
            ) -> None:
                self.url = url

        c = Container()
        c.register(Service)
        result = c.visualise()
        assert "DB_URL" in result

    def test_optional_uses_dashed_edge(self) -> None:
        class OptService:
            def __init__(self, repo: Repository | None = None) -> None:
                self.repo = repo

        c = Container()
        c.register(Repository)
        c.register(OptService)
        result = c.visualise()
        assert "-.->" in result
