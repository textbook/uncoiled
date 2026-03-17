from uncoiled import Scope, ScopeManager, SingletonScope, TransientScope


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
