from __future__ import annotations

import json

import pytest

from modeldiff.checks import CheckResult, evaluate, register_check

# --- exact -------------------------------------------------------------------


def test_exact_strips_whitespace_by_default(make_case):
    case = make_case(type="exact", expected="Hello")
    assert evaluate(case, "  Hello\n").passed


def test_exact_is_case_sensitive_by_default(make_case):
    result = evaluate(make_case(type="exact", expected="Hello"), "hello")
    assert not result.passed
    assert result.reason == (
        "output differs from expected at character 0: expected 'Hello', got 'hello'"
    )


def test_exact_ignore_case_and_no_strip(make_case):
    case = make_case(type="exact", expected="Hello", options={"ignore_case": True, "strip": False})
    assert evaluate(case, "HELLO").passed
    assert not evaluate(case, "HELLO ").passed


def test_exact_reports_position_for_prefix(make_case):
    result = evaluate(make_case(type="exact", expected="abc"), "abcdef")
    assert not result.passed
    assert result.reason == (
        "output differs from expected at character 3: expected 'abc', got 'abcdef'"
    )


def test_exact_normalize_whitespace(make_case):
    case_without = make_case(type="exact", expected="Hello world")
    assert not evaluate(case_without, "Hello\r\n  world").passed

    case_with = make_case(
        type="exact",
        expected="Hello world",
        options={"normalize_whitespace": True},
    )
    assert evaluate(case_with, "Hello\r\n  world").passed


def test_exact_normalize_whitespace_reports_position_on_normalized_text(make_case):
    case = make_case(
        type="exact",
        expected="Hello world",
        options={"normalize_whitespace": True},
    )
    result = evaluate(case, "Hello\r\n  there")
    assert not result.passed
    assert result.reason == (
        "output differs from expected at character 6: expected 'Hello world', got 'Hello there'"
    )


@pytest.mark.parametrize(
    ("before", "after", "position", "expected_excerpt", "actual_excerpt"),
    [
        ("", "r" * 25, 0, "X" + "r" * 20 + "...", "Y" + "r" * 20 + "..."),
        (
            "l" * 25,
            "r" * 25,
            25,
            "..." + "l" * 20 + "X" + "r" * 20 + "...",
            "..." + "l" * 20 + "Y" + "r" * 20 + "...",
        ),
        ("l" * 25, "", 25, "..." + "l" * 20 + "X", "..." + "l" * 20 + "Y"),
        (
            "l" * 20,
            "r" * 20,
            20,
            "l" * 20 + "X" + "r" * 20,
            "l" * 20 + "Y" + "r" * 20,
        ),
        (
            "l" * 21,
            "r" * 21,
            21,
            "..." + "l" * 20 + "X" + "r" * 20 + "...",
            "..." + "l" * 20 + "Y" + "r" * 20 + "...",
        ),
    ],
    ids=["start", "middle", "end", "exact-window", "one-beyond-window"],
)
def test_exact_excerpt_shows_context_and_marks_only_cut_text(
    make_case, before, after, position, expected_excerpt, actual_excerpt
):
    result = evaluate(make_case(type="exact", expected=before + "X" + after), before + "Y" + after)
    assert not result.passed
    assert result.reason == (
        f"output differs from expected at character {position}: "
        f"expected {expected_excerpt!r}, got {actual_excerpt!r}"
    )


@pytest.mark.parametrize(
    ("expected", "actual", "position"),
    [("", "hello", 0), ("hello", "", 0), ("abcdef", "abc", 3)],
)
def test_exact_excerpt_when_one_string_ends(make_case, expected, actual, position):
    result = evaluate(make_case(type="exact", expected=expected), actual)
    assert not result.passed
    assert result.reason == (
        f"output differs from expected at character {position}: expected {expected!r}, got {actual!r}"
    )


@pytest.mark.parametrize("expected_ends_first", [True, False])
def test_exact_excerpt_for_long_prefix(make_case, expected_ends_first):
    shorter, longer = "a" * 30, "a" * 30 + "b" * 30
    short_excerpt, long_excerpt = "..." + "a" * 20, "..." + "a" * 20 + "b" * 21 + "..."
    expected, actual = (shorter, longer) if expected_ends_first else (longer, shorter)
    expected_excerpt, actual_excerpt = (
        (short_excerpt, long_excerpt) if expected_ends_first else (long_excerpt, short_excerpt)
    )
    result = evaluate(make_case(type="exact", expected=expected), actual)
    assert not result.passed
    assert result.reason == (
        "output differs from expected at character 30: "
        f"expected {expected_excerpt!r}, got {actual_excerpt!r}"
    )


@pytest.mark.parametrize(
    ("expected", "actual", "options", "position", "expected_excerpt", "actual_excerpt"),
    [
        ("  ABCx\n", " \tABCy \r\n", {}, 3, "ABCx", "ABCy"),
        (" hello", "\thello", {"strip": False}, 0, " hello", "\thello"),
        (
            "  Straße \tBLUE\n",
            "\tSTRASSE\n  GREEN ",
            {"ignore_case": True, "normalize_whitespace": True},
            8,
            "strasse blue",
            "strasse green",
        ),
    ],
    ids=["strip", "no-strip", "casefold-and-whitespace"],
)
def test_exact_excerpt_uses_normalized_text(
    make_case, expected, actual, options, position, expected_excerpt, actual_excerpt
):
    result = evaluate(make_case(type="exact", expected=expected, options=options), actual)
    assert not result.passed
    assert result.reason == (
        f"output differs from expected at character {position}: "
        f"expected {expected_excerpt!r}, got {actual_excerpt!r}"
    )


def test_exact_excerpt_quotes_newlines_backslashes_and_unicode(make_case):
    expected, actual = "a\n'\"\\é🙂X", "a\n'\"\\é🙂Y"
    result = evaluate(make_case(type="exact", expected=expected), actual)
    assert not result.passed
    assert result.reason == (
        f"output differs from expected at character 7: expected {expected!r}, got {actual!r}"
    )
    assert "\n" not in result.reason
    assert "\\n" in result.reason


@pytest.mark.parametrize(
    "fill", ["a", "\x00", "\U000e0001"], ids=["ascii", "nul", "unicode-escape"]
)
def test_exact_excerpt_stays_bounded_for_long_strings(make_case, fill):
    before, after = fill * 100_000, fill * 100_000
    result = evaluate(make_case(type="exact", expected=before + "X" + after), before + "Y" + after)
    expected_excerpt = "..." + fill * 20 + "X" + fill * 20 + "..."
    actual_excerpt = "..." + fill * 20 + "Y" + fill * 20 + "..."
    assert not result.passed
    assert result.reason == (
        "output differs from expected at character 100000: "
        f"expected {expected_excerpt!r}, got {actual_excerpt!r}"
    )
    assert len(result.reason) < 1_000


def test_exact_normalized_match_has_no_failure_excerpt(make_case):
    case = make_case(
        type="exact",
        expected=" Straße \n BLUE ",
        options={"ignore_case": True, "normalize_whitespace": True},
    )
    assert evaluate(case, "STRASSE\tblue") == CheckResult(True)


# --- json --------------------------------------------------------------------

SCHEMA = {
    "type": "object",
    "required": ["name", "age"],
    "properties": {"name": {"type": "string"}, "age": {"type": "integer", "minimum": 0}},
}


def test_json_without_schema_only_checks_parsing(make_case):
    case = make_case(type="json")
    assert evaluate(case, "[1, 2]").passed
    result = evaluate(case, "```json\n{}\n```")
    assert not result.passed and result.reason.startswith("output is not valid JSON")


def test_json_schema_pass_and_fail(make_case):
    case = make_case(type="json", schema=SCHEMA)
    assert evaluate(case, '{"name": "a", "age": 3}').passed
    result = evaluate(case, '{"name": 5, "age": -1}')
    assert not result.passed
    assert "age: -1 is less than the minimum of 0" in result.reason
    assert "name: 5 is not of type 'string'" in result.reason


def test_json_schema_missing_property(make_case):
    result = evaluate(make_case(type="json", schema=SCHEMA), '{"name": "a"}')
    assert "'age' is a required property" in result.reason


def test_json_schema_error_list_is_truncated(make_case):
    schema = {"type": "object", "properties": {k: {"type": "string"} for k in "abcdefg"}}
    output = json.dumps({k: 1 for k in "abcdefg"})
    result = evaluate(make_case(type="json", schema=schema), output)
    assert "... and 2 more" in result.reason


def test_json_extract_code_fence(make_case):
    case = make_case(type="json", options={"extract": "code_fence"})
    assert evaluate(case, '```json\n{"a":1}\n```').passed
    assert evaluate(case, '```\n{"a":1}\n```').passed
    assert evaluate(case, 'Here is the result:\n```json\n{"a":1}\n```\nDone.').passed
    assert evaluate(case, '{"a": 1}').passed
    # Multiple fenced blocks fall back to parsing the whole output
    multi = '```json\n{"a": 1}\n```\n```json\n{"b": 2}\n```'
    assert not evaluate(case, multi).passed


def test_required_fields_and_tool_call_extract_code_fence(make_case):
    rf_case = make_case(
        type="required_fields",
        required=["user.name"],
        options={"extract": "code_fence"},
    )
    assert evaluate(rf_case, '```json\n{"user": {"name": "a"}}\n```').passed

    tc_case = make_case(
        type="tool_call",
        expected={"name": "get", "arguments": {"id": "1"}},
        options={"extract": "code_fence"},
    )
    assert evaluate(tc_case, '```json\n{"name": "get", "arguments": {"id": "1"}}\n```').passed


# --- classification ----------------------------------------------------------


def test_classification_normalizes_case_and_whitespace(make_case):
    case = make_case(type="classification", expected="Positive")
    result = evaluate(case, " positive\n")
    assert result.passed
    assert result.details == {"predicted_label": "positive", "expected_label": "positive"}


def test_classification_mismatch_records_labels(make_case):
    result = evaluate(make_case(type="classification", expected="billing"), "technical")
    assert not result.passed
    assert result.details["predicted_label"] == "technical"
    assert result.reason == "predicted 'technical', expected 'billing'"


def test_classification_rejects_label_outside_allowed_set(make_case):
    case = make_case(type="classification", expected="yes", labels=["yes", "no"])
    result = evaluate(case, "Yes, definitely")
    assert "is not an allowed label" in result.reason


def test_classification_without_normalize_is_exact(make_case):
    case = make_case(type="classification", expected="Yes", options={"normalize": False})
    assert not evaluate(case, "yes").passed


# --- required_fields ---------------------------------------------------------


def test_required_fields_nested_and_list_paths(make_case):
    case = make_case(type="required_fields", required=["user.name", "items.0.sku"])
    assert evaluate(case, '{"user": {"name": "a"}, "items": [{"sku": "x"}]}').passed
    result = evaluate(case, '{"user": {}, "items": []}')
    assert result.reason == "missing field(s): user.name, items.0.sku"


def test_required_fields_null_value_counts_as_present(make_case):
    case = make_case(type="required_fields", required=["a"])
    assert evaluate(case, '{"a": null}').passed


def test_required_fields_values(make_case):
    case = make_case(type="required_fields", values={"status": "ok", "count": 2})
    assert evaluate(case, '{"status": "ok", "count": 2}').passed
    result = evaluate(case, '{"status": "error", "count": 2}')
    assert result.reason == "wrong value(s): status='error' (expected 'ok')"


def test_required_fields_values_compare_json_types(make_case):
    # Regression: Python says True == 1 and 1 == 1.0, JSON does not.
    case = make_case(type="required_fields", values={"active": True, "qty": 1.0})
    assert evaluate(case, '{"active": true, "qty": 1}').passed
    result = evaluate(case, '{"active": 1, "qty": 1}')
    assert result.reason == "wrong value(s): active=1 (expected True)"
    assert not evaluate(case, '{"active": false, "qty": 1}').passed


def test_required_fields_values_strict_types_are_recursive(make_case):
    case = make_case(type="required_fields", values={"items": [{"active": True}]})
    assert evaluate(case, '{"items": [{"active": true}]}').passed
    assert not evaluate(case, '{"items": [{"active": 1}]}').passed


def test_required_fields_path_in_both_lists_reported_once(make_case):
    # Regression: a path in both `required` and `values` was listed twice.
    case = make_case(type="required_fields", required=["city"], values={"city": "Pune"})
    result = evaluate(case, "{}")
    assert result.reason == "missing field(s): city"


def test_required_fields_on_non_object_output(make_case):
    case = make_case(type="required_fields", required=["a"])
    assert evaluate(case, "[]").reason == "missing field(s): a"
    assert evaluate(case, "not json").reason.startswith("output is not valid JSON")


# --- tool_call ---------------------------------------------------------------


def test_tool_call_plain_shape(make_case):
    case = make_case(type="tool_call", expected={"name": "get", "arguments": {"id": "1"}})
    result = evaluate(case, '{"name": "get", "arguments": {"id": "1"}}')
    assert result.passed and result.details == {"tool_name": "get"}


def test_tool_call_function_shape_with_string_arguments(make_case):
    case = make_case(type="tool_call", expected={"name": "get", "arguments": {"id": "1"}})
    output = json.dumps({"function": {"name": "get", "arguments": json.dumps({"id": "1"})}})
    assert evaluate(case, output).passed


def test_tool_call_list_wrapper(make_case):
    case = make_case(type="tool_call", expected={"name": "get"})
    assert evaluate(case, '{"tool_calls": [{"name": "get", "arguments": {}}]}').passed
    result = evaluate(case, '[{"name": "get"}, {"name": "get"}]')
    assert result.reason == "expected exactly one tool call, got 2"


def test_tool_call_wrong_name(make_case):
    result = evaluate(
        make_case(type="tool_call", expected={"name": "refund"}), '{"name": "lookup"}'
    )
    assert result.reason == "called tool 'lookup', expected 'refund'"


def test_tool_call_argument_differences_are_listed(make_case):
    case = make_case(type="tool_call", expected={"name": "f", "arguments": {"id": "7", "x": 1}})
    result = evaluate(case, '{"name": "f", "arguments": {"id": 7, "y": 2}}')
    assert result.reason == "tool arguments differ: id=7 (expected '7'), x missing, y unexpected"


def test_tool_call_arguments_compare_json_types(make_case):
    case = make_case(type="tool_call", expected={"name": "f", "arguments": {"qty": 1}})
    assert evaluate(case, '{"name": "f", "arguments": {"qty": 1.0}}').passed
    result = evaluate(case, '{"name": "f", "arguments": {"qty": true}}')
    assert result.reason == "tool arguments differ: qty=True (expected 1)"


def test_tool_call_argument_schema(make_case):
    schema = {
        "type": "object",
        "required": ["amount"],
        "properties": {"amount": {"type": "number"}},
    }
    case = make_case(type="tool_call", expected={"name": "f", "arguments_schema": schema})
    assert evaluate(case, '{"name": "f", "arguments": {"amount": 5}}').passed
    result = evaluate(case, '{"name": "f", "arguments": {"amount": "5"}}')
    assert "tool arguments failed schema: amount: '5' is not of type 'number'" == result.reason


def test_tool_call_malformed_inputs(make_case):
    case = make_case(type="tool_call", expected={"name": "f"})
    assert "no string 'name'" in evaluate(case, '{"tool": "f"}').reason
    assert (
        "arguments are not valid JSON"
        in evaluate(case, '{"name": "f", "arguments": "{bad"}').reason
    )
    assert "must be an object" in evaluate(case, '{"name": "f", "arguments": [1]}').reason


# --- custom ------------------------------------------------------------------


def test_custom_check_returning_bool(make_case):
    @register_check("always_true")
    def always_true(case, output):
        return output == "ok"

    case = make_case(type="custom", check="always_true")
    assert evaluate(case, "ok").passed
    assert evaluate(case, "no").reason == "custom check 'always_true' failed"


def test_custom_check_receives_params(make_case):
    @register_check("max_words")
    def max_words(case, output):
        n = len(output.split())
        return CheckResult(n <= case.params["limit"], f"{n} words", {"words": n})

    case = make_case(type="custom", check="max_words", params={"limit": 2})
    assert evaluate(case, "one two").passed
    result = evaluate(case, "one two three")
    assert not result.passed and result.details == {"words": 3}


def test_custom_check_bad_return_type(make_case):
    @register_check("bad_return")
    def bad(case, output):
        return "yes"

    with pytest.raises(TypeError, match="expected CheckResult or bool"):
        evaluate(make_case(type="custom", check="bad_return"), "x")


def test_registering_a_different_function_twice_fails():
    @register_check("dup")
    def first(case, output):
        return True

    with pytest.raises(ValueError, match="already registered"):

        @register_check("dup")
        def second(case, output):
            return True
