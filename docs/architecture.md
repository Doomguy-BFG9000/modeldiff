# Architecture and design decisions

## Pipeline

```
suite.yaml ─┐
            ├─> runner ──> result.json (baseline) ─┐
config.yaml ┘                                       ├─> compare ──> report (text / md / json)
                     result.json (candidate) ──────┘
```

| Module | Responsibility | Depends on |
| --- | --- | --- |
| `cases.py` | Read YAML/JSON, validate suite structure, build `Suite`/`TestCase`, compute the suite hash | `checks.validate_case` |
| `checks.py` | Per-type validation of case definitions, evaluation of outputs, custom check registry | `cases.TestCase` |
| `config.py` | Validate run configs, redact secret-looking keys | `cases.read_document` |
| `providers.py` | Turn a case into an output (`replay`, `ollama`) | `config`, `cases` |
| `runner.py` | Run every case, time it, evaluate it, build a `RunResult` | `checks`, `providers`, `results` |
| `results.py` | `CaseResult`/`RunResult`, the `modeldiff.run/v1` file format and its validation | none |
| `compare.py` | Match two runs by case ID and classify each case | `results` |
| `report.py` | Render a run or a comparison | `compare`, `results` |
| `cli.py` | Argument parsing, plugin loading, exit codes | everything above |

`compare` and `report` depend only on result files, not on suites or providers. You can therefore compare runs produced elsewhere, as long as they follow the result format.

## Decisions

**Explicit criteria only.** Each case type has a deterministic pass rule. ModelDiff does not use similarity scores or model-graded evaluation, because those need tuning and external models, and their results are hard to reproduce offline. A changed output that still passes is reported as a *behavior change* for a human to review. It is never counted as a regression.

**Regression means pass to not-pass.** `error` (the provider failed, or a custom check raised) is treated as not passing, so a candidate that crashes on a case counts as a regression. A case that fails in both runs is "still failing", not a regression, even if the failure reason changed.

**Suite hash.** Every result file records a SHA-256 of the normalized case definitions. `compare` refuses runs whose hashes differ unless `--allow-suite-mismatch` is passed, because comparing outcomes under different criteria gives misleading answers. Reformatting the suite file or switching between YAML and JSON does not change the hash.

**Recorded vs measured latency.** The replay provider would otherwise always measure near-zero latency. Recorded files can therefore carry the latency observed when the output was captured, and each result marks its `duration_source`. Latency never fails a comparison unless `--fail-on-latency` is given, because single timings are noisy.

**Strict schemas for input files.** Suite and config files reject unknown keys (`additionalProperties: false`), so a typo such as `expectd` is reported instead of silently ignored. Result files are read leniently: unknown fields are ignored, so that newer files can still be compared by older versions.

**No plugin framework.** Custom checks are plain functions registered with a decorator and loaded with `--plugin`. Providers are a small `Protocol` (`generate`, `describe`), and new ones are added in `providers.py` and `build_provider`. This can be revisited if the number of providers grows.

**Standard library HTTP.** The Ollama adapter uses `urllib`, so supporting it adds no dependency.

## Dependencies

| Dependency | Why |
| --- | --- |
| `jsonschema` | Validates suites, configs, and result files, and powers the `json` and `tool_call` checks. JSON Schema is the format users already write for structured outputs. |
| `PyYAML` | YAML suites are easier to read and review than JSON for multi-line prompts. Only `safe_load` is used. |
| `psutil` (optional, `[memory]`) | Process RSS. Optional because it is a compiled package and the metric is supplementary. |
| `pytest`, `ruff` (dev only) | Tests and linting/formatting. |

## Adding a check type

1. Add the type name to `CASE_TYPES` and any new fields to `SUITE_SCHEMA` in `cases.py`.
2. Add a `_validate_<type>` and an `_eval_<type>` function in `checks.py` and register them in `_VALIDATORS` and `_EVALUATORS`.
3. If the check produces a value that is useful to compare across runs, put it in `CheckResult.details` and teach `compare.py` about it (see `predicted_label`).
4. Add tests for both validation and evaluation, and document the type in the README.

Before adding a built-in type, consider whether a custom check is enough.

## Adding a provider

1. Implement a class with `name`, `generate(case) -> ProviderResponse`, and `describe() -> dict`. Raise `ProviderError` for any failure that should mark the case as `error` without aborting the run.
2. Add its config keys to `CONFIG_SCHEMA` (with an `if/then` block for required keys) and construct it in `build_provider`.
3. Test it with mocked I/O. Tests must not need a running server or a downloaded model.
