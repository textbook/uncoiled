import contextvars

import pytest

from uncoiled import RequestScope, Scope, ScopeManager, SingletonScope, TransientScope


class TestSingletonScope:
    def test_scope_type(self) -> None:
        assert SingletonScope().scope is Scope.SINGLETON

    def test_get_returns_none_when_empty(self) -> None:
        scope = SingletonScope()
        assert scope.get(str) is None

    def test_put_and_get(self) -> None:
        scope = SingletonScope()
        scope.put(str, "hello")
        assert scope.get(str) == "hello"

    def test_returns_same_instance(self) -> None:
        scope = SingletonScope()
        obj = object()
        scope.put(object, obj)
        assert scope.get(object) is obj

    def test_clear(self) -> None:
        scope = SingletonScope()
        scope.put(str, "hello")
        scope.clear()
        assert scope.get(str) is None

    def test_conforms_to_protocol(self) -> None:
        assert isinstance(SingletonScope(), ScopeManager)

    def test_qualifier_isolation(self) -> None:
        scope = SingletonScope()
        scope.put(str, "default")
        scope.put(str, "primary", qualifier="primary")
        assert scope.get(str) == "default"
        assert scope.get(str, qualifier="primary") == "primary"


class TestTransientScope:
    def test_scope_type(self) -> None:
        assert TransientScope().scope is Scope.TRANSIENT

    def test_get_always_returns_none(self) -> None:
        scope = TransientScope()
        scope.put(str, "hello")
        assert scope.get(str) is None

    def test_clear_is_noop(self) -> None:
        scope = TransientScope()
        scope.clear()

    def test_conforms_to_protocol(self) -> None:
        assert isinstance(TransientScope(), ScopeManager)


class TestRequestScope:
    def test_scope_type(self) -> None:
        assert RequestScope().scope is Scope.REQUEST

    def test_conforms_to_protocol(self) -> None:
        assert isinstance(RequestScope(), ScopeManager)

    def test_get_returns_none_outside_context(self) -> None:
        scope = RequestScope()
        assert scope.get(str) is None

    def test_put_raises_outside_context(self) -> None:
        scope = RequestScope()
        with pytest.raises(LookupError, match="request context"):
            scope.put(str, "hello")

    def test_put_and_get_within_context(self) -> None:
        scope = RequestScope()
        with scope.context():
            scope.put(str, "hello")
            assert scope.get(str) == "hello"

    def test_qualifier_isolation(self) -> None:
        scope = RequestScope()
        with scope.context():
            scope.put(str, "default")
            scope.put(str, "primary", qualifier="primary")
            assert scope.get(str) == "default"
            assert scope.get(str, qualifier="primary") == "primary"

    def test_clear(self) -> None:
        scope = RequestScope()
        with scope.context():
            scope.put(str, "hello")
            scope.clear()
            assert scope.get(str) is None

    def test_context_exit_cleans_up(self) -> None:
        scope = RequestScope()
        with scope.context():
            scope.put(str, "hello")
        assert scope.get(str) is None

    def test_remove_outside_context_is_noop(self) -> None:
        scope = RequestScope()
        scope.remove(str)  # should not raise

    def test_remove_within_context(self) -> None:
        scope = RequestScope()
        with scope.context():
            scope.put(str, "hello")
            scope.remove(str)
            assert scope.get(str) is None

    def test_scope_is_property(self) -> None:
        scope = RequestScope()
        assert isinstance(type(scope).scope, property)

    def test_context_isolation(self) -> None:
        scope = RequestScope()
        results: list[str] = []

        def run_in_context(value: str) -> None:
            with scope.context():
                scope.put(str, value)
                results.append(scope.get(str))  # type: ignore[arg-type]

        ctx1 = contextvars.copy_context()
        ctx2 = contextvars.copy_context()
        ctx1.run(run_in_context, "first")
        ctx2.run(run_in_context, "second")
        assert results == ["first", "second"]
