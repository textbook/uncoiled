import pytest

from uncoiled import Container, Inject


class Repository:
    pass


class MockRepo(Repository):
    pass


class TestInject:
    def test_getitem_resolves_type(self) -> None:
        c = Container()
        c.register(Repository)
        c.start()
        inject = Inject(c)
        assert isinstance(inject[Repository], Repository)

    def test_getitem_raises_for_missing(self) -> None:
        c = Container()
        c.start()
        inject = Inject(c)
        with pytest.raises(LookupError):
            inject[Repository]


class TestPluginFixtures:
    """Test plugin fixtures using pytester."""

    @pytest.fixture
    def configured_pytester(self, pytester: pytest.Pytester) -> pytest.Pytester:
        pytester.makeconftest(
            """\
import pytest
from uncoiled import Container

class Repo:
    pass

class MockRepo(Repo):
    pass

@pytest.fixture(scope="session")
def uncoiled_container():
    c = Container()
    c.register(Repo)
    c.start()
    yield c
    c.close()
"""
        )
        return pytester

    def test_inject_fixture(self, configured_pytester: pytest.Pytester) -> None:
        configured_pytester.makepyfile(
            """\
def test_inject(inject):
    from uncoiled import Inject
    assert isinstance(inject, Inject)
"""
        )
        result = configured_pytester.runpytest()
        result.assert_outcomes(passed=1)

    def test_inject_getitem(self, configured_pytester: pytest.Pytester) -> None:
        configured_pytester.makepyfile(
            """\
def test_resolve(inject):
    from conftest import Repo
    assert isinstance(inject[Repo], Repo)
"""
        )
        result = configured_pytester.runpytest()
        result.assert_outcomes(passed=1)

    def test_override_marker(self, configured_pytester: pytest.Pytester) -> None:
        configured_pytester.makepyfile(
            """\
import pytest
from conftest import Repo, MockRepo

@pytest.mark.uncoiled_override(Repo, MockRepo)
def test_overridden(inject):
    assert isinstance(inject[Repo], MockRepo)

def test_not_overridden(inject):
    result = inject[Repo]
    assert type(result) is Repo
"""
        )
        result = configured_pytester.runpytest()
        result.assert_outcomes(passed=2)

    def test_override_marker_with_instance(
        self, configured_pytester: pytest.Pytester
    ) -> None:
        configured_pytester.makepyfile(
            """\
import pytest
from conftest import Repo

sentinel = Repo()

@pytest.mark.uncoiled_override(Repo, sentinel)
def test_overridden_instance(inject):
    assert inject[Repo] is sentinel
"""
        )
        result = configured_pytester.runpytest()
        result.assert_outcomes(passed=1)
