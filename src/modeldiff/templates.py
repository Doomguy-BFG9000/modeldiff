"""Small offline starter files written by ``modeldiff init``."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from modeldiff.errors import ValidationError

_SUITE = """# Replace these example prompts and checks with your own cases.
suite: starter
description: A small offline starter suite.
cases:
  - id: greeting-exact
    type: exact
    input: "Reply with exactly: Hello!"
    expected: "Hello!"
  - id: status-json
    type: json
    input: 'Return a JSON object with status set to "ok".'
    schema:
      type: object
      required: [status]
      properties:
        status: {const: ok}
      additionalProperties: false
"""

_RECORDED = (
    json.dumps(
        {
            "metadata": {
                "description": "Hand-written placeholder outputs, not real model outputs; replace with your own recordings."
            },
            "outputs": {"greeting-exact": "Hello!", "status-json": '{"status": "ok"}'},
        },
        indent=2,
    )
    + "\n"
)

STARTER_FILES = {"suite.yaml": _SUITE}
for _name in ("baseline", "candidate"):
    STARTER_FILES[f"configs/{_name}.yaml"] = (
        f"id: {_name}\nprovider: replay\noutputs: ../recorded/{_name}.json\n"
        "# Replace the hand-written placeholders with your own recorded outputs.\n"
    )
    STARTER_FILES[f"recorded/{_name}.json"] = _RECORDED


def _write_file(path: Path, content: str, *, force: bool) -> None:
    if not force:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(content)
        return
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".modeldiff-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        # Replace the directory entry rather than truncating a possibly hard-linked file.
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def create_starter(directory: Path, *, force: bool = False) -> None:
    """Write the five starter files, preserving unrelated files when forced."""
    try:
        if directory.exists():
            if not directory.is_dir():
                raise ValidationError(str(directory), ["target must be a directory"])
            if not force and any(directory.iterdir()):
                raise ValidationError(
                    str(directory), ["directory is not empty; use --force to replace starter files"]
                )

        # Check every destination before replacing any existing starter file.
        root = directory.resolve()
        for relative in STARTER_FILES:
            path = directory / relative
            if not path.resolve().is_relative_to(root):
                raise ValidationError(
                    str(path), ["starter destination must stay inside the target"]
                )
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise ValidationError(str(path), ["starter destination must be a regular file"])
            for parent in path.parents:
                if parent == directory:
                    break
                if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                    raise ValidationError(
                        str(parent), ["starter parent must be a regular directory"]
                    )

        directory.mkdir(parents=True, exist_ok=True)
        for relative, content in STARTER_FILES.items():
            path = directory / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            _write_file(path, content, force=force)
    except OSError as exc:
        raise ValidationError(str(directory), [f"cannot create starter: {exc.strerror}"]) from None
