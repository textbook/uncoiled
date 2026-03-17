from uncoiled import ComponentMetadata, Scope, component


def _get_metadata(cls: type) -> ComponentMetadata:
    return cls.__uncoiled__  # ty: ignore[unresolved-attribute]


class TestComponentDecorator:
    def test_bare_decorator(self) -> None:
        @component
        class MyService:
            pass

        assert hasattr(MyService, "__uncoiled__")
        assert _get_metadata(MyService) == ComponentMetadata()

    def test_decorator_with_scope(self) -> None:
        @component(scope=Scope.TRANSIENT)
        class MyService:
            pass

        assert _get_metadata(MyService).scope is Scope.TRANSIENT

    def test_decorator_with_qualifier(self) -> None:
        @component(qualifier="special")
        class MyService:
            pass

        assert _get_metadata(MyService).qualifier == "special"

    def test_decorator_with_all_options(self) -> None:
        @component(scope=Scope.TRANSIENT, qualifier="special")
        class MyService:
            pass

        expected = ComponentMetadata(
            scope=Scope.TRANSIENT,
            qualifier="special",
        )
        assert _get_metadata(MyService) == expected

    def test_does_not_modify_class(self) -> None:
        @component
        class MyService:
            def greet(self) -> str:
                return "hello"

        assert MyService().greet() == "hello"

    def test_default_scope_is_singleton(self) -> None:
        @component
        class MyService:
            pass

        assert _get_metadata(MyService).scope is Scope.SINGLETON

    def test_metadata_is_frozen(self) -> None:
        meta = ComponentMetadata()
        try:
            meta.scope = Scope.TRANSIENT  # ty: ignore[invalid-assignment]
        except AttributeError:
            pass
        else:
            msg = "Expected frozen dataclass to reject mutation"
            raise AssertionError(msg)
