import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest

from uncoiled import DictSource, bind_config, config_properties

FALSY_VALUES = ["false", "0", "no", "off", "False", "FALSE", "No", "OFF"]
TRUTHY_VALUES = ["true", "1", "yes", "on", "True", "TRUE", "Yes", "ON"]

MYSQL_PORT = 3306
POSTGRES_PORT = 5432


@config_properties("db")
@dataclass(frozen=True)
class DbConfig:
    host: str = "localhost"
    port: int = POSTGRES_PORT


@config_properties("app")
@dataclass(frozen=True)
class AppConfig:
    name: str = "myapp"
    debug: bool = False
    tags: list[str] = ""  # ty: ignore[invalid-assignment]


class TestConfigProperties:
    def test_binds_from_source(self) -> None:
        source = DictSource({"db.host": "remotehost", "db.port": "3306"})
        config = bind_config(DbConfig, source)
        assert config.host == "remotehost"
        assert config.port == MYSQL_PORT

    def test_uses_defaults(self) -> None:
        source = DictSource({})
        config = bind_config(DbConfig, source)
        assert config.host == "localhost"
        assert config.port == POSTGRES_PORT

    def test_partial_override(self) -> None:
        source = DictSource({"db.host": "custom"})
        config = bind_config(DbConfig, source)
        assert config.host == "custom"
        assert config.port == POSTGRES_PORT

    def test_bool_coercion(self) -> None:
        source = DictSource({"app.name": "test", "app.debug": "true"})
        config = bind_config(AppConfig, source)
        assert config.debug is True

    def test_list_coercion(self) -> None:
        source = DictSource({"app.name": "test", "app.tags": "a, b, c"})
        config = bind_config(AppConfig, source)
        assert config.tags == ["a", "b", "c"]

    def test_path_coercion(self) -> None:
        @config_properties("fs")
        @dataclass(frozen=True)
        class FsConfig:
            root: Path = Path()

        source = DictSource({"fs.root": "/opt/data"})
        config = bind_config(FsConfig, source)
        assert config.root == Path("/opt/data")

    @pytest.mark.parametrize("value", FALSY_VALUES)
    def test_bool_coercion_falsy(self, value: str) -> None:
        source = DictSource({"app.name": "test", "app.debug": value})
        config = bind_config(AppConfig, source)
        assert config.debug is False

    @pytest.mark.parametrize("value", TRUTHY_VALUES)
    def test_bool_coercion_truthy(self, value: str) -> None:
        source = DictSource({"app.name": "test", "app.debug": value})
        config = bind_config(AppConfig, source)
        assert config.debug is True

    def test_bool_coercion_invalid_raises(self) -> None:
        source = DictSource({"app.name": "test", "app.debug": "maybe"})
        with pytest.raises(ValueError, match="Cannot coerce"):
            bind_config(AppConfig, source)

    def test_missing_required_raises(self) -> None:
        @config_properties("svc")
        @dataclass(frozen=True)
        class SvcConfig:
            url: str

        source = DictSource({})
        with pytest.raises(ValueError, match="Missing required"):
            bind_config(SvcConfig, source)

    def test_unsupported_type_lists_supported(self) -> None:
        @config_properties("svc")
        @dataclass(frozen=True)
        class SvcConfig:
            id: uuid.UUID

        source = DictSource({"svc.id": "abc"})
        with pytest.raises(ValueError, match="Cannot coerce") as exc_info:
            bind_config(SvcConfig, source)
        cause = exc_info.value.__cause__
        assert cause is not None
        assert "Supported types:" in str(cause)

    def test_bind_config_invalid_int_shows_key(self) -> None:
        source = DictSource({"db.host": "localhost", "db.port": "not_a_number"})
        with pytest.raises(
            ValueError,
            match=r"Cannot coerce config key 'db\.port'.*to int",
        ):
            bind_config(DbConfig, source)

    def test_bind_config_invalid_bool_shows_key(self) -> None:
        source = DictSource({"app.name": "test", "app.debug": "not_a_bool"})
        with pytest.raises(
            ValueError,
            match=r"Cannot coerce config key 'app\.debug'.*to bool",
        ):
            bind_config(AppConfig, source)
