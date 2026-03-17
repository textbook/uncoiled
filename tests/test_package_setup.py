import pathlib
import tomllib
from typing import Any

import pytest

from uncoiled import __version__

ROOT_DIR = (pathlib.Path(__file__).parent / "..").resolve()


@pytest.fixture
def pyproject_file() -> dict[str, Any]:
    with (ROOT_DIR / "pyproject.toml").open(mode="rb") as f:
        return tomllib.load(f)


def test_version(pyproject_file: dict[str, Any]) -> None:
    assert __version__ == pyproject_file["project"]["version"]
