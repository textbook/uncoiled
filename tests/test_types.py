from uncoiled import (
    MISSING,
    AsyncDisposable,
    Disposable,
    Scope,
)


class TestScope:
    def test_values(self) -> None:
        assert Scope.SINGLETON.value == "singleton"
        assert Scope.TRANSIENT.value == "transient"
        assert Scope.REQUEST.value == "request"

    def test_default_is_singleton(self) -> None:
        assert next(iter(Scope)) is Scope.SINGLETON


class TestMissingSentinel:
    def test_repr(self) -> None:
        assert repr(MISSING) == "<MISSING>"

    def test_is_not_none(self) -> None:
        assert MISSING is not None


class TestDisposable:
    def test_matches_class_with_close(self) -> None:
        class Resource:
            def close(self) -> None: ...

        assert isinstance(Resource(), Disposable)

    def test_rejects_class_without_close(self) -> None:
        class NotResource: ...

        assert not isinstance(NotResource(), Disposable)


class TestAsyncDisposable:
    def test_matches_class_with_aclose(self) -> None:
        class AsyncResource:
            async def aclose(self) -> None: ...

        assert isinstance(AsyncResource(), AsyncDisposable)

    def test_rejects_class_without_aclose(self) -> None:
        class NotAsync:
            def close(self) -> None: ...

        assert not isinstance(NotAsync(), AsyncDisposable)
