"""Exception hierarchy for dependency resolution errors."""

from __future__ import annotations

import enum
from dataclasses import dataclass


class FailureKind(enum.Enum):
    """Classification of dependency resolution failures."""

    MISSING = "missing"
    CIRCULAR = "circular"


@dataclass(frozen=True)
class ResolutionFailure:
    """A single failure encountered during dependency resolution."""

    kind: FailureKind
    message: str
    suggestion: str
    component: type | None = None
    parameter: str | None = None

    def __str__(self) -> str:
        """Format as a human-readable error description."""
        lines = [self.message, f"    To fix: {self.suggestion}"]
        return "\n".join(lines)


class DependencyResolutionError(Exception):
    """Raised when the dependency graph cannot be resolved.

    Aggregates all failures into a single error rather than failing on the first.
    """

    def __init__(self, failures: list[ResolutionFailure]) -> None:
        self.failures = failures
        super().__init__(str(self))

    def __str__(self) -> str:
        """Format all failures into a numbered list."""
        count = len(self.failures)
        suffix = "s" if count != 1 else ""
        header = f"Cannot build dependency graph ({count} failure{suffix}):"
        items = [
            f"\n  {i}. {failure}" for i, failure in enumerate(self.failures, start=1)
        ]
        return header + "".join(items)
