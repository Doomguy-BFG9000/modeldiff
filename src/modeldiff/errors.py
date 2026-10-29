"""Exception types raised by ModelDiff."""

from __future__ import annotations


class ModelDiffError(Exception):
    """Base class for all ModelDiff errors."""


class ValidationError(ModelDiffError):
    """A suite, config, or result file is malformed.

    ``problems`` holds one human-readable message per issue so that every
    problem in a file can be reported at once instead of one at a time.
    """

    def __init__(self, source: str, problems: list[str]) -> None:
        self.source = source
        self.problems = problems
        joined = "\n".join(f"  - {p}" for p in problems)
        super().__init__(f"{source} is invalid:\n{joined}")


class ProviderError(ModelDiffError):
    """An inference provider failed to produce an output."""
