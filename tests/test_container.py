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
