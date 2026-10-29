"""ModelDiff: regression testing for local AI."""

from modeldiff._version import __version__
from modeldiff.cases import Suite, TestCase, load_suite
from modeldiff.checks import CheckResult, register_check
from modeldiff.compare import Comparison, compare_runs
from modeldiff.errors import ModelDiffError, ProviderError, ValidationError
from modeldiff.results import CaseResult, RunResult, load_run, save_run

__all__ = [
    "CaseResult",
    "CheckResult",
    "Comparison",
    "ModelDiffError",
    "ProviderError",
    "RunResult",
    "Suite",
    "TestCase",
    "ValidationError",
    "__version__",
    "compare_runs",
    "load_run",
    "load_suite",
    "register_check",
    "save_run",
]
