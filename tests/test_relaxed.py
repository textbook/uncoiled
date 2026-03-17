import pytest

from uncoiled import normalise


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("MY_DB_HOST", "my.db.host"),
        ("my-db-host", "my.db.host"),
        ("my.db.host", "my.db.host"),
        ("MY-DB_HOST", "my.db.host"),
        ("simple", "simple"),
        ("UPPER", "upper"),
        ("a.b-c_d", "a.b.c.d"),
    ],
)
def test_normalise(key: str, expected: str) -> None:
    assert normalise(key) == expected
