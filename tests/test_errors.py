from uncoiled import (
    DependencyResolutionError,
    FailureKind,
    ResolutionFailure,
)


class TestResolutionFailure:
    def test_str_includes_message_and_suggestion(self) -> None:
        failure = ResolutionFailure(
            kind=FailureKind.MISSING,
            message="No component of type 'UserRepository' is registered.",
            suggestion="Add @component to UserRepository.",
        )
        text = str(failure)
        assert "No component of type 'UserRepository' is registered." in text
        assert "To fix: Add @component to UserRepository." in text

    def test_optional_fields_default_to_none(self) -> None:
        failure = ResolutionFailure(
            kind=FailureKind.CIRCULAR,
            message="Cycle detected.",
            suggestion="Break the cycle.",
        )
        assert failure.component is None
        assert failure.parameter is None

    def test_frozen(self) -> None:
        failure = ResolutionFailure(
            kind=FailureKind.MISSING,
            message="msg",
            suggestion="fix",
        )
        try:
            failure.message = "changed"  # ty: ignore[invalid-assignment]
        except AttributeError:
            pass
        else:
            msg = "Expected frozen dataclass to reject mutation"
            raise AssertionError(msg)


class TestDependencyResolutionError:
    def test_single_failure_message(self) -> None:
        failure = ResolutionFailure(
            kind=FailureKind.MISSING,
            message="Missing dependency for UserService.__init__.",
            suggestion="Register UserRepository.",
        )
        error = DependencyResolutionError([failure])
        text = str(error)
        assert "1 failure)" in text
        assert "1. Missing dependency" in text

    def test_multiple_failures_message(self) -> None:
        failures = [
            ResolutionFailure(
                kind=FailureKind.CIRCULAR,
                message="Circular dependency detected: A -> B -> A.",
                suggestion="Break the cycle by introducing an interface.",
            ),
            ResolutionFailure(
                kind=FailureKind.MISSING,
                message="Missing dependency for UserService.__init__.",
                suggestion="Register UserRepository.",
            ),
        ]
        error = DependencyResolutionError(failures)
        text = str(error)
        assert "2 failures)" in text
        assert "1. Circular dependency" in text
        assert "2. Missing dependency" in text

    def test_failures_accessible(self) -> None:
        failure = ResolutionFailure(
            kind=FailureKind.MISSING,
            message="Missing.",
            suggestion="Register a component.",
            component=int,
            parameter="value",
        )
        error = DependencyResolutionError([failure])
        assert error.failures == [failure]
        assert error.failures[0].component is int
        assert error.failures[0].parameter == "value"
