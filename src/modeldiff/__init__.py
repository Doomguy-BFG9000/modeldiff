"""ModelDiff: regression testing for local AI."""

from modeldiff.cases import Suite, TestCase, load_suite
from modeldiff.checks import CheckResult, register_check
from modeldiff.errors import ModelDiffError, ProviderError, ValidationError
from modeldiff.results import CaseResult, RunResult, load_run, save_run
from modeldiff._version import __version__

__all__ = [
    "CaseResult",
    "CheckResult",
    "ModelDiffError",
    "ProviderError",
    "RunResult",
    "Suite",
    "TestCase",
    "ValidationError",
    "load_run",
    "load_suite",
    "register_check",
    "save_run",
    "__version__",
]
