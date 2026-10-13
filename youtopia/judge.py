"""Run a user's solution against a problem's hidden tests, LeetCode style.

The solution runs in a separate Python process: isolated mode, an empty temporary working
directory, a minimal environment (no API keys), and CPU, memory and wall-clock limits.
That keeps runaway code from hanging YOUtopia. It is not a security sandbox: the code runs
with your permissions, so only submit code you wrote or trust.
"""

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from youtopia.problems import Problem

TIME_LIMIT_S = 10
MEMORY_LIMIT_BYTES = 1024 * 1024 * 1024
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_SOLUTION_BYTES = 1024 * 1024


class JudgeError(ValueError):
    """The submission can't be judged at all (missing file, not Python…)."""


@dataclass
class CaseResult:
    number: int
    passed: bool
    args: list
    expected: object
    got: str | None = None  # JSON of what the function returned
    error: str | None = None


@dataclass
class Verdict:
    total: int
    cases: list[CaseResult] = field(default_factory=list)
    load_error: str | None = None
    timed_out: bool = False

    @property
    def passed(self) -> int:
        return sum(c.passed for c in self.cases)

    @property
    def accepted(self) -> bool:
        return self.load_error is None and self.total > 0 and self.passed == self.total

    @property
    def first_failure(self) -> CaseResult | None:
        return next((c for c in self.cases if not c.passed), None)


def check_solution_file(path: Path) -> Path:
    path = path.expanduser()
    if not path.is_file():
        raise JudgeError(f"No file at {path}.")
    if path.suffix != ".py":
        raise JudgeError("Solutions must be Python files ending in .py.")
    if path.stat().st_size > MAX_SOLUTION_BYTES:
        raise JudgeError("That file is too large to be a solution.")
    return path.resolve()


def run_tests(solution: Path, problem: Problem, time_limit_s: float = TIME_LIMIT_S) -> Verdict:
    solution = check_solution_file(solution)
    harness = resources.files("youtopia").joinpath("judge_harness.py")
    with (
        tempfile.TemporaryDirectory(prefix="youtopia-judge-") as tmp,
        resources.as_file(harness) as harness_path,
    ):
        cases_path = Path(tmp) / "cases.json"
        results_path = Path(tmp) / "results.json"
        cases_path.write_text(
            json.dumps(
                {
                    "function": problem.function,
                    "tests": list(problem.tests),
                    "compare": problem.compare,
                    "tolerance": problem.tolerance,
                    "solution_dir": str(solution.parent),
                }
            ),
            encoding="utf-8",
        )
        command = [sys.executable, "-I", str(harness_path), str(solution), str(cases_path),
                   str(results_path)]  # fmt: skip
        timed_out = False
        try:
            subprocess.run(  # noqa: S603 - fixed argv, no shell
                command,
                cwd=tmp,
                env=_minimal_env(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=time_limit_s,
                preexec_fn=_limit_resources if os.name == "posix" else None,  # noqa: PLW1509
                check=False,
            )
        except subprocess.TimeoutExpired:
            timed_out = True
        raw = _read_results(results_path)
    return _verdict(problem, raw, timed_out)


def _minimal_env() -> dict[str, str]:
    env = {"PATH": os.defpath, "PYTHONIOENCODING": "utf-8", "PYTHONHASHSEED": "0"}
    for name in ("SYSTEMROOT", "TEMP", "TMP"):  # Windows needs these to start Python
        if name in os.environ:
            env[name] = os.environ[name]
    return env


def _limit_resources() -> None:  # pragma: no cover - runs in the child process
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (TIME_LIMIT_S + 1, TIME_LIMIT_S + 1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE_BYTES, MAX_FILE_BYTES))


def _read_results(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"load_error": "The solution crashed before any test ran.", "cases": []}


def _verdict(problem: Problem, raw: dict, timed_out: bool) -> Verdict:
    verdict = Verdict(total=len(problem.tests), load_error=raw.get("load_error"))
    for number, (case, result) in enumerate(
        zip(problem.tests, raw.get("cases", []), strict=False), start=1
    ):
        verdict.cases.append(
            CaseResult(
                number=number,
                passed=bool(result.get("passed")),
                args=case["args"],
                expected=case["expected"],
                got=result.get("got"),
                error=result.get("error"),
            )
        )
    for number in range(len(verdict.cases) + 1, verdict.total + 1):
        case = problem.tests[number - 1]
        reason = "Time limit exceeded" if timed_out else "Not run (the solution stopped early)"
        verdict.cases.append(
            CaseResult(number, False, case["args"], case["expected"], error=reason)
        )
    verdict.timed_out = timed_out
    return verdict
