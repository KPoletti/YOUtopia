import os

import pytest

from youtopia import judge
from youtopia.problems import make_problem

ADD = make_problem(
    function="add_up",
    signature="def add_up(a: int, b: int) -> int:",
    tests=[
        {"args": [1, 2], "expected": 3},
        {"args": [0, 0], "expected": 0},
        {"args": [-4, 9], "expected": 5},
    ],
)


def run(tmp_path, code, problem=ADD, **kwargs):
    path = tmp_path / "solution.py"
    path.write_text(code)
    return judge.run_tests(path, problem, **kwargs)


def test_correct_solution_is_accepted(tmp_path):
    verdict = run(tmp_path, "def add_up(a, b):\n    return a + b\n")
    assert verdict.accepted
    assert (verdict.passed, verdict.total) == (3, 3)


def test_wrong_answer_shows_the_first_failure(tmp_path):
    verdict = run(tmp_path, "def add_up(a, b):\n    return a + b if a >= 0 else 0\n")
    assert not verdict.accepted
    assert verdict.passed == 2
    failure = verdict.first_failure
    assert (failure.number, failure.args, failure.expected, failure.got) == (3, [-4, 9], 5, "0")


def test_exceptions_fail_only_their_case(tmp_path):
    verdict = run(tmp_path, "def add_up(a, b):\n    if a == 0: raise ValueError('nope')\n"
                            "    return a + b\n")  # fmt: skip
    assert verdict.passed == 2
    assert verdict.first_failure.error == "ValueError: nope"


@pytest.mark.parametrize(
    "code, message",
    [
        ("def add_up(a, b)\n    return a + b\n", "SyntaxError"),
        ("def other(a, b):\n    return a + b\n", "add_up"),
        ("raise SystemExit(3)\n", "SystemExit"),
        ("add_up = 5\n", "isn't a function"),
    ],
)
def test_load_errors(tmp_path, code, message):
    verdict = run(tmp_path, code)
    assert not verdict.accepted
    assert message in verdict.load_error


def test_timeouts_keep_finished_cases(tmp_path):
    code = "def add_up(a, b):\n    while a == 0:\n        pass\n    return a + b\n"
    verdict = run(tmp_path, code, time_limit_s=2)
    assert verdict.timed_out
    assert verdict.cases[0].passed
    assert verdict.cases[1].error == "Time limit exceeded"
    assert verdict.passed == 1


def test_unordered_and_tolerance(tmp_path):
    pairs = make_problem(
        function="pairs",
        signature="def pairs(n: int) -> list[list[int]]:",
        tests=[{"args": [2], "expected": [[0, 1], [1, 0]]}],
        compare="unordered",
    )
    assert run(tmp_path, "def pairs(n):\n    return [(1, 0), (0, 1)]\n", pairs).accepted

    approx = make_problem(
        function="third",
        signature="def third(x: float) -> float:",
        tests=[{"args": [1], "expected": 0.33}],
        tolerance=0.01,
    )
    assert run(tmp_path, "def third(x):\n    return x / 3\n", approx).accepted


def test_bools_and_ints_are_not_interchangeable(tmp_path):
    flag = make_problem(
        function="flag",
        signature="def flag(n: int) -> bool:",
        tests=[{"args": [1], "expected": True}],
    )
    assert not run(tmp_path, "def flag(n):\n    return 1\n", flag).accepted
    assert run(tmp_path, "def flag(n):\n    return n == 1\n", flag).accepted


def test_solution_runs_without_secrets_in_an_empty_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTOPIA_API_KEY", "sk-secret-0123456789")
    monkeypatch.chdir(tmp_path)
    spy = make_problem(
        function="spy",
        signature="def spy(n: int) -> list:",
        tests=[{"args": [0], "expected": [None, []]}],
    )
    code = (
        "import os\n"
        "def spy(n):\n"
        "    open('dropped.txt', 'w').write('x')\n"
        "    return [os.environ.get('YOUTOPIA_API_KEY'), "
        "sorted(f for f in os.listdir('.') if f.endswith('.py'))]\n"
    )
    verdict = run(tmp_path, code, spy)
    assert verdict.accepted, verdict.first_failure
    assert not (tmp_path / "dropped.txt").exists()  # it ran in a throwaway directory
    assert "YOUTOPIA_API_KEY" in os.environ


@pytest.mark.parametrize("name, message", [("missing.py", "No file"), ("notes.txt", ".py")])
def test_unusable_files(tmp_path, name, message):
    if name.endswith(".txt"):
        (tmp_path / name).write_text("hi")
    with pytest.raises(judge.JudgeError, match=message):
        judge.run_tests(tmp_path / name, ADD)
