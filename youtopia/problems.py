"""LeetCode-style problems: the function to write, its signature and the hidden tests.

Shared by the template library, AI drafts, the judge and starter files. Validation is
strict because AI-written problems end up in a Python file the user runs (`starter`):
the signature allows only names, type hints and punctuation, so it can't carry code.
"""

import json
import keyword
import math
import re
from dataclasses import dataclass
from typing import Any

FUNCTION_RE = re.compile(r"^[a-z_][a-z0-9_]{0,39}$")
# `def name(params) -> type:` with plain names and type hints only. No defaults, calls,
# quotes or decorators, so nothing in it can run code when the file is imported.
SIGNATURE_RE = re.compile(
    r"^def (?P<name>[a-z_][a-z0-9_]{0,39})\((?P<params>[A-Za-z0-9_ ,:\[\]|.]*)\)"
    r"(?: -> [A-Za-z0-9_ \[\],|.]+)?:$"
)
COMPARE_MODES = ("exact", "unordered")
MAX_TESTS = 12
MAX_ARGS = 6
MAX_CASE_CHARS = 4000
MAX_TOLERANCE = 1000.0


class ProblemError(ValueError):
    """An invalid problem definition."""


@dataclass(frozen=True)
class Problem:
    function: str
    signature: str
    tests: tuple[dict[str, Any], ...]  # each {"args": [...], "expected": ...}
    compare: str = "exact"
    tolerance: float | None = None  # absolute tolerance for numbers; None = near-exact

    def to_json(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "function": self.function,
            "signature": self.signature,
            "tests": [dict(t) for t in self.tests],
            "compare": self.compare,
        }
        if self.tolerance is not None:
            data["tolerance"] = self.tolerance
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any], *, min_tests: int = 1) -> "Problem":
        return make_problem(
            function=data.get("function"),
            signature=data.get("signature"),
            tests=data.get("tests"),
            compare=data.get("compare", "exact"),
            tolerance=data.get("tolerance"),
            min_tests=min_tests,
        )


def make_problem(
    *,
    function: object,
    signature: object,
    tests: object,
    compare: object = "exact",
    tolerance: object = None,
    min_tests: int = 1,
) -> Problem:
    """Validate every part of a problem. Raises ProblemError with the first issue found."""
    if not isinstance(function, str) or not FUNCTION_RE.match(function):
        raise ProblemError(f"bad function name {function!r}")
    if function.startswith("__") or keyword.iskeyword(function):
        raise ProblemError(f"function name {function!r} isn't allowed")
    if not isinstance(signature, str) or not (match := SIGNATURE_RE.match(signature)):
        raise ProblemError(f"bad signature {signature!r}")
    if match["name"] != function:
        raise ProblemError("signature doesn't define the named function")
    if compare not in COMPARE_MODES:
        raise ProblemError(f"compare must be one of {COMPARE_MODES}")
    if tolerance is not None:
        if (
            isinstance(tolerance, bool) or not isinstance(tolerance, int | float)
            or not 0 < tolerance <= MAX_TOLERANCE or not math.isfinite(tolerance)
        ):  # fmt: skip
            raise ProblemError("tolerance must be a positive number")
        tolerance = float(tolerance)
    if not isinstance(tests, list | tuple) or not min_tests <= len(tests) <= MAX_TESTS:
        raise ProblemError(f"need {min_tests} to {MAX_TESTS} tests")
    cleaned = []
    for case in tests:
        if not isinstance(case, dict) or set(case) != {"args", "expected"}:
            raise ProblemError("each test needs exactly 'args' and 'expected'")
        if not isinstance(case["args"], list) or len(case["args"]) > MAX_ARGS:
            raise ProblemError(f"'args' must be a list of at most {MAX_ARGS} arguments")
        try:
            text = json.dumps(case, allow_nan=False)
        except (TypeError, ValueError):
            raise ProblemError("tests must be plain JSON values") from None
        if len(text) > MAX_CASE_CHARS:
            raise ProblemError("a test case is too large")
        cleaned.append(json.loads(text))
    return Problem(function, signature, tuple(cleaned), str(compare), tolerance)


def starter_source(title: str, instructions: str, problem: Problem) -> str:
    """A solution skeleton. Untrusted text only ever lands in comments."""
    comment = "\n".join(f"# {line}".rstrip() for line in f"{title}\n\n{instructions}".splitlines())
    first = problem.tests[0]["args"] if problem.tests else []
    call = f"{problem.function}({', '.join(repr(a) for a in first)})"
    return (
        f"{comment}\n\n\n"
        f"{problem.signature}\n"
        "    # Write your solution here.\n"
        "    raise NotImplementedError\n\n\n"
        'if __name__ == "__main__":\n'
        f"    print({call})\n"
    )
