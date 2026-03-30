import logging
import types as t

import pytest

from uncoiled import Container, DotEnvSource, Scope, YamlSource


class Repository:
    pass


class UserService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo


class TestContainerLogging:
    def test_register_logs_component(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG, logger="uncoiled"):
            c = Container()
            c.register(Repository)
        assert "Registered component Repository" in caplog.text
        assert "scope=singleton" in caplog.text

    def test_register_factory_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        def create_repo() -> Repository:
            return Repository()

        with caplog.at_level(logging.DEBUG, logger="uncoiled"):
            c = Container()
            c.register_factory(
                create_repo,
                return_type=Repository,
                scope=Scope.TRANSIENT,
            )
        assert "Registered factory for Repository" in caplog.text
        assert "scope=transient" in caplog.text

    def test_register_instance_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG, logger="uncoiled"):
            c = Container()
            c.register_instance(Repository())
        assert "Registered instance of Repository" in caplog.text

    def test_start_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        c = Container()
        c.register(Repository)
        with caplog.at_level(logging.DEBUG, logger="uncoiled"):
            c.start()
        assert "Container starting" in caplog.text
        assert "Container started" in caplog.text

    def test_close_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        c = Container()
        c.register(Repository)
        c.start()
        with caplog.at_level(logging.DEBUG, logger="uncoiled"):
            c.close()
        assert "Container closing" in caplog.text

    def test_resolve_logs_creation(self, caplog: pytest.LogCaptureFixture) -> None:
        c = Container()
        c.register(Repository)
        c.register(UserService)
        c.start()
        with caplog.at_level(logging.DEBUG, logger="uncoiled"):
            c.get(UserService)
        # UserService was already created during start, so no "Created" log
        # but a transient would log on each get:
        c.register(Repository, scope=Scope.TRANSIENT, replace=True)
        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="uncoiled"):
            c.get(Repository)
        assert "Created Repository" in caplog.text
        assert "scope=transient" in caplog.text

    def test_scan_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        mod = t.ModuleType("test_scan_log_mod")

        with caplog.at_level(logging.DEBUG, logger="uncoiled"):
            c = Container()
            c.scan(mod)
        assert "Scanning module test_scan_log_mod" in caplog.text

    def test_override_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        c = Container()
        c.register(Repository)
        c.start()
        with (
            caplog.at_level(logging.DEBUG, logger="uncoiled"),
            c.override(
                Repository,
                Repository(),
            ),
        ):
            pass
        assert "Overriding Repository" in caplog.text

    def test_fork_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        c = Container()
        c.register(Repository)
        with caplog.at_level(logging.DEBUG, logger="uncoiled"):
            c.fork()
        assert "Forked container" in caplog.text

    def test_empty_list_dependency_warns(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        class Handler:
            pass

        class Bus:
            def __init__(self, handlers: list[Handler]) -> None:
                self.handlers = handlers

        c = Container()
        c.register(Bus)
        with caplog.at_level(logging.WARNING, logger="uncoiled"):
            c.start()
        assert "No implementations found" in caplog.text
        assert "list[Handler]" in caplog.text


class TestAutoScopeLogging:
    def test_auto_resolution_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        c = Container()
        c.register(Repository)
        c.register(UserService, scope=Scope.AUTO)
        with caplog.at_level(logging.DEBUG, logger="uncoiled"):
            c.start()
        assert "AUTO scope resolved: UserService -> singleton" in caplog.text


class TestLifecycleLogging:
    def test_init_hook_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        class Service:
            def setup(self) -> None:
                pass

        c = Container()
        c.register(Service, init_method="setup")
        with caplog.at_level(logging.DEBUG, logger="uncoiled"):
            c.start()
        assert "Calling Service.setup()" in caplog.text

    def test_destroy_hook_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        class Service:
            def cleanup(self) -> None:
                pass

        c = Container()
        c.register(Service, destroy_method="cleanup")
        c.start()
        with caplog.at_level(logging.DEBUG, logger="uncoiled"):
            c.close()
        assert "Calling Service.cleanup()" in caplog.text


class TestConfigSourceLogging:
    def test_dotenv_missing_file_warns(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="uncoiled"):
            DotEnvSource("/nonexistent/.env")
        assert "file not found" in caplog.text

    def test_yaml_missing_file_warns(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="uncoiled"):
            YamlSource("/nonexistent/config.yaml")
        assert "file not found" in caplog.text
