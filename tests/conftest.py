from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from modeldiff.cases import TestCase
from modeldiff.checks import unregister_check

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "quickstart"


@pytest.fixture
def example_dir() -> Path:
    return EXAMPLE


@pytest.fixture
def write_yaml(tmp_path: Path) -> Callable[[str, Any], Path]:
    def write(name: str, data: Any) -> Path:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return path

    return write


@pytest.fixture
def write_json(tmp_path: Path) -> Callable[[str, Any], Path]:
    def write(name: str, data: Any) -> Path:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    return write


@pytest.fixture
def make_case() -> Callable[..., TestCase]:
    def make(**kwargs: Any) -> TestCase:
        kwargs.setdefault("id", "c1")
        kwargs.setdefault("input", "prompt")
        return TestCase(**kwargs)

    return make


@pytest.fixture(autouse=True)
def _clean_custom_checks():
    """Custom checks are global; drop ones registered by a test."""
    yield
    for name in ("max_words", "always_true", "boom", "bad_return", "dup"):
        unregister_check(name)
