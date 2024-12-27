import typing_extensions as tx

from uncoiled import Container, EnvVar


def test_handles_annotated_string_types():
    key = "APP_NAME"
    value = "test-app"
    container = Container().overload(EnvVar, lambda: {key: value})
    result = container.get(tx.Annotated[str, EnvVar[key]])
    assert result == value
