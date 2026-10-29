"""Custom checks used by the quickstart suite.

Load with: modeldiff run ... --plugin examples/quickstart/checks.py
"""

from modeldiff import CheckResult, register_check


@register_check("max_words")
def max_words(case, output):
    limit = case.params["limit"]
    words = len(output.split())
    if words > limit:
        return CheckResult(False, f"{words} words, limit is {limit}", {"words": words})
    return CheckResult(True, None, {"words": words})
