from uncoiled import ComponentMetadata, Scope, component, factory


def _get_metadata(target: object) -> ComponentMetadata:
    return target.__uncoiled__  # ty: ignore[unresolved-attribute]


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

    def test_decorator_with_provides(self) -> None:
        class Base:
            pass

        @component(provides=Base)
        class Impl(Base):
            pass

        assert _get_metadata(Impl).provides is Base

    def test_provides_defaults_to_none(self) -> None:
        @component
        class MyService:
            pass

        assert _get_metadata(MyService).provides is None

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


class _Dummy:
    pass


class TestFactoryOnFunction:
    def test_bare_decorator_attaches_metadata(self) -> None:
        @factory
        def create() -> _Dummy:
            return _Dummy()

        assert hasattr(create, "__uncoiled__")
        assert _get_metadata(create) == ComponentMetadata()

    def test_decorator_with_scope(self) -> None:
        @factory(scope=Scope.TRANSIENT)
        def create() -> _Dummy:
            return _Dummy()

        assert _get_metadata(create).scope is Scope.TRANSIENT

    def test_decorator_with_qualifier(self) -> None:
        @factory(qualifier="special")
        def create() -> _Dummy:
            return _Dummy()

        assert _get_metadata(create).qualifier == "special"

    def test_decorator_with_provides(self) -> None:
        @factory(provides=_Dummy)
        def create_impl() -> _Dummy:
            return _Dummy()

        assert _get_metadata(create_impl).provides is _Dummy

    def test_does_not_modify_function(self) -> None:
        @factory
        def create() -> _Dummy:
            return _Dummy()

        assert isinstance(create(), _Dummy)  # ty: ignore[call-non-callable]

    def test_decorator_with_all_options(self) -> None:
        @factory(scope=Scope.TRANSIENT, qualifier="special", provides=_Dummy)
        def create() -> _Dummy:
            return _Dummy()

        expected = ComponentMetadata(
            scope=Scope.TRANSIENT,
            qualifier="special",
            provides=_Dummy,
        )
        assert _get_metadata(create) == expected


class TestFactoryOnClassmethod:
    def test_factory_then_classmethod(self) -> None:
        class MyFactory:
            @factory
            @classmethod
            def create(cls) -> _Dummy:
                return _Dummy()

        desc = MyFactory.__dict__["create"]
        assert isinstance(desc, classmethod)
        assert hasattr(desc.__func__, "__uncoiled__")
        assert _get_metadata(desc.__func__) == ComponentMetadata()

    def test_classmethod_then_factory(self) -> None:
        class MyFactory:
            @classmethod
            @factory
            def create(cls) -> _Dummy:
                return _Dummy()

        desc = MyFactory.__dict__["create"]
        assert isinstance(desc, classmethod)
        assert hasattr(desc.__func__, "__uncoiled__")
        assert _get_metadata(desc.__func__) == ComponentMetadata()

    def test_with_arguments(self) -> None:
        class MyFactory:
            @factory(scope=Scope.TRANSIENT, qualifier="x")
            @classmethod
            def create(cls) -> _Dummy:
                return _Dummy()

        meta = _get_metadata(MyFactory.__dict__["create"].__func__)
        expected = ComponentMetadata(scope=Scope.TRANSIENT, qualifier="x")
        assert meta == expected

    def test_classmethod_still_callable(self) -> None:
        class MyFactory:
            @factory
            @classmethod
            def create(cls) -> _Dummy:
                return _Dummy()

        assert isinstance(MyFactory.create(), _Dummy)  # ty: ignore[call-non-callable]
