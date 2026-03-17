from typing import Annotated, get_type_hints

from uncoiled import Qualifier


class TestQualifier:
    def test_name(self) -> None:
        q = Qualifier("postgres")
        assert q.name == "postgres"

    def test_equality(self) -> None:
        assert Qualifier("a") == Qualifier("a")
        assert Qualifier("a") != Qualifier("b")

    def test_frozen(self) -> None:
        q = Qualifier("x")
        try:
            q.name = "y"  # ty: ignore[invalid-assignment]
        except AttributeError:
            pass
        else:
            msg = "Expected frozen dataclass to reject mutation"
            raise AssertionError(msg)

    def test_usable_in_annotated(self) -> None:
        class Service:
            def __init__(
                self,
                repo: Annotated[str, Qualifier("postgres")],
            ) -> None:
                self.repo = repo

        hints = get_type_hints(Service.__init__, include_extras=True)
        assert hints["repo"].__metadata__[0] == Qualifier("postgres")

    def test_hashable(self) -> None:
        qualifiers = {Qualifier("a"), Qualifier("a"), Qualifier("b")}
        expected = 2
        assert len(qualifiers) == expected
