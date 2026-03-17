import types

import pytest

from uncoiled import Container, DependencyResolutionError, Scope, component


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

    def test_register_rejects_unsupported_scope(self) -> None:
        c = Container()
        with pytest.raises(ValueError, match="request"):
            c.register(Repository, scope=Scope.REQUEST)

    def test_register_factory_rejects_unsupported_scope(self) -> None:
        c = Container()
        with pytest.raises(ValueError, match="request"):
            c.register_factory(Repository, return_type=Repository, scope=Scope.REQUEST)


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
            def __init__(self, repo: Repository | None = sentinel) -> None:  # type: ignore[assignment]
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
        child.register(MockRepo, provides=Repository)
        assert isinstance(child.get(Repository), MockRepo)
        assert not isinstance(c.get(Repository), MockRepo)


class TestContainerScan:
    def test_scan_finds_decorated_classes(self) -> None:
        @component
        class ScanService:
            pass

        mod = types.ModuleType("test_scan_mod")
        mod.ScanService = ScanService  # type: ignore[attr-defined]

        c = Container()
        c.scan(mod)
        assert isinstance(c.get(ScanService), ScanService)
