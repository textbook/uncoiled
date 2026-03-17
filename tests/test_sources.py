import os
import pathlib

from uncoiled import (
    ConfigSource,
    DictSource,
    DotEnvSource,
    EnvSource,
    LayeredSource,
    YamlSource,
)


class TestDictSource:
    def test_get_existing_key(self) -> None:
        source = DictSource({"db.host": "localhost"})
        assert source.get("db.host") == "localhost"

    def test_get_missing_key(self) -> None:
        source = DictSource({"db.host": "localhost"})
        assert source.get("db.port") is None

    def test_normalises_keys(self) -> None:
        source = DictSource({"DB_HOST": "localhost"})
        assert source.get("db.host") == "localhost"

    def test_conforms_to_protocol(self) -> None:
        assert isinstance(DictSource({}), ConfigSource)


class TestEnvSource:
    def test_get_from_env(self) -> None:
        os.environ["TEST_DB_HOST"] = "localhost"
        try:
            source = EnvSource()
            assert source.get("TEST_DB_HOST") == "localhost"
        finally:
            del os.environ["TEST_DB_HOST"]

    def test_get_dotted_key(self) -> None:
        os.environ["DB_HOST"] = "localhost"
        try:
            source = EnvSource()
            assert source.get("db.host") == "localhost"
        finally:
            del os.environ["DB_HOST"]

    def test_get_missing(self) -> None:
        source = EnvSource()
        assert source.get("NONEXISTENT_KEY_12345") is None

    def test_conforms_to_protocol(self) -> None:
        assert isinstance(EnvSource(), ConfigSource)


class TestDotEnvSource:
    def test_parse_simple(self, tmp_path: pathlib.Path) -> None:
        p = tmp_path / ".env"
        p.write_text("DB_HOST=localhost\nDB_PORT=5432\n")
        source = DotEnvSource(str(p))
        assert source.get("db.host") == "localhost"
        assert source.get("db.port") == "5432"

    def test_parse_quoted_values(self, tmp_path: pathlib.Path) -> None:
        p = tmp_path / ".env"
        p.write_text("DB_HOST=\"localhost\"\nDB_NAME='mydb'\n")
        source = DotEnvSource(str(p))
        assert source.get("db.host") == "localhost"
        assert source.get("db.name") == "mydb"

    def test_skip_comments_and_blanks(self, tmp_path: pathlib.Path) -> None:
        p = tmp_path / ".env"
        p.write_text("# comment\n\nDB_HOST=localhost\n")
        source = DotEnvSource(str(p))
        assert source.get("db.host") == "localhost"

    def test_missing_file(self) -> None:
        source = DotEnvSource("/nonexistent/.env")
        assert source.get("anything") is None

    def test_conforms_to_protocol(self) -> None:
        assert isinstance(DotEnvSource("/nonexistent"), ConfigSource)


class TestLayeredSource:
    def test_first_source_wins(self) -> None:
        s1 = DictSource({"db.host": "from-s1"})
        s2 = DictSource({"db.host": "from-s2"})
        layered = LayeredSource(s1, s2)
        assert layered.get("db.host") == "from-s1"

    def test_falls_through(self) -> None:
        s1 = DictSource({})
        s2 = DictSource({"db.host": "from-s2"})
        layered = LayeredSource(s1, s2)
        assert layered.get("db.host") == "from-s2"

    def test_all_miss(self) -> None:
        layered = LayeredSource(DictSource({}), DictSource({}))
        assert layered.get("missing") is None

    def test_conforms_to_protocol(self) -> None:
        assert isinstance(LayeredSource(), ConfigSource)


class TestYamlSource:
    def test_flat_keys(self, tmp_path: pathlib.Path) -> None:
        p = tmp_path / "config.yml"
        p.write_text("db_host: localhost\ndb_port: 5432\n")
        source = YamlSource(str(p))
        assert source.get("db.host") == "localhost"
        assert source.get("db.port") == "5432"

    def test_nested_keys(self, tmp_path: pathlib.Path) -> None:
        p = tmp_path / "config.yml"
        p.write_text("db:\n  host: localhost\n  port: 5432\n")
        source = YamlSource(str(p))
        assert source.get("db.host") == "localhost"
        assert source.get("db.port") == "5432"

    def test_missing_file(self) -> None:
        source = YamlSource("/nonexistent/config.yml")
        assert source.get("anything") is None

    def test_conforms_to_protocol(self, tmp_path: pathlib.Path) -> None:
        p = tmp_path / "config.yml"
        p.write_text("")
        assert isinstance(YamlSource(str(p)), ConfigSource)

    def test_normalises_keys(self, tmp_path: pathlib.Path) -> None:
        p = tmp_path / "config.yml"
        p.write_text("DB_HOST: localhost\n")
        source = YamlSource(str(p))
        assert source.get("db.host") == "localhost"
