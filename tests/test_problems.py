import pytest

from youtopia.problems import Problem, ProblemError, make_problem, starter_source

TESTS = [{"args": [1], "expected": 1}]


def problem(**overrides):
    fields = {"function": "solve", "signature": "def solve(n: int) -> int:", "tests": TESTS}
    return make_problem(**(fields | overrides))


@pytest.mark.parametrize(
    "signature",
    [
        "def solve(n: int) -> int:",
        "def solve(xs: list[int], k: int) -> list[list[int]]:",
        "def solve(grid: list[str]) -> str | None:",
        "def solve() -> bool:",
    ],
)
def test_good_signatures(signature):
    assert problem(signature=signature).signature == signature


@pytest.mark.parametrize(
    "signature",
    [
        "def solve(n=__import__('os').system('echo hi')):",  # defaults run at import
        "def solve(n: int) -> int:\n    import os",  # extra lines
        "def other(n: int) -> int:",  # wrong name
        "@decorator\ndef solve(n):",
        "def solve(n: print('x')) -> int:",  # calls in annotations
        "def solve(n: 'str') -> int:",
        "lambda n: n",
        "",
    ],
)
def test_signatures_that_could_run_code_are_rejected(signature):
    with pytest.raises(ProblemError):
        problem(signature=signature)


@pytest.mark.parametrize(
    "overrides",
    [
        {"function": "__init__", "signature": "def __init__(n: int) -> int:"},
        {"function": "class", "signature": "def class(n: int) -> int:"},
        {"function": "Bad-Name"},
        {"tests": []},
        {"tests": [{"args": 1, "expected": 1}]},
        {"tests": [{"args": [1]}]},
        {"tests": [{"args": [1], "expected": 1, "extra": 2}]},
        {"tests": [{"args": [float("nan")], "expected": 1}]},
        {"tests": [{"args": ["x" * 5000], "expected": 1}]},
        {"tests": TESTS * 13},
        {"compare": "fuzzy"},
        {"tolerance": -1},
        {"tolerance": True},
    ],
)
def test_bad_problems_are_rejected(overrides):
    with pytest.raises(ProblemError):
        problem(**overrides)


def test_round_trips_through_json():
    original = problem(compare="unordered", tolerance=0.5)
    assert Problem.from_json(original.to_json()) == original


def test_starter_is_valid_python_with_untrusted_text_only_in_comments(tmp_path):
    nasty = 'Title\r__import__("os").system("echo pwned")\n""" print("injected")'
    source = starter_source(nasty, nasty, problem())
    for line in source.splitlines():
        if "pwned" in line or "injected" in line:
            assert line.startswith("#"), line
    namespace = {}
    exec(compile(source, "starter.py", "exec"), namespace)  # defines solve, runs nothing else
    with pytest.raises(NotImplementedError):
        namespace["solve"](1)
