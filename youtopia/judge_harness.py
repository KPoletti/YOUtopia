"""Runs one solution file against hidden tests. Executed as a separate process by judge.py.

Usage: python -I judge_harness.py SOLUTION.py CASES.json RESULTS.json

Standard library only. Results are rewritten after every case, so a timeout still
reports the cases that finished.
"""

import copy
import importlib.util
import json
import math
import sys
import traceback

MAX_SHOWN = 300


def _normalise(value):
    if isinstance(value, tuple | list):
        return [_normalise(v) for v in value]
    if isinstance(value, set | frozenset):
        return sorted((_normalise(v) for v in value), key=_key)
    if isinstance(value, dict):
        return {str(k): _normalise(v) for k, v in value.items()}
    return value


def _key(value):
    return json.dumps(value, sort_keys=True, default=repr)


def _equal(got, expected, tolerance):
    if isinstance(got, bool) or isinstance(expected, bool):
        return type(got) is type(expected) and got == expected
    if isinstance(got, int | float) and isinstance(expected, int | float):
        if tolerance is not None:
            return abs(got - expected) <= tolerance + 1e-12
        return math.isclose(got, expected, rel_tol=1e-6, abs_tol=1e-9)
    if isinstance(got, list) and isinstance(expected, list):
        return len(got) == len(expected) and all(
            _equal(g, e, tolerance) for g, e in zip(got, expected, strict=True)
        )
    if isinstance(got, dict) and isinstance(expected, dict):
        return got.keys() == expected.keys() and all(
            _equal(got[k], expected[k], tolerance) for k in got
        )
    return got == expected


def _shown(value):
    try:
        text = json.dumps(value, default=repr)
    except (TypeError, ValueError, RecursionError):
        text = repr(value)
    return text if len(text) <= MAX_SHOWN else text[: MAX_SHOWN - 1] + "…"


def _write(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def main():
    solution_path, cases_path, results_path = sys.argv[1:4]
    with open(cases_path, encoding="utf-8") as f:
        spec = json.load(f)
    payload = {"load_error": None, "cases": []}
    _write(results_path, payload)

    sys.path.insert(0, spec["solution_dir"])
    try:
        module_spec = importlib.util.spec_from_file_location("solution", solution_path)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        func = getattr(module, spec["function"])
        if not callable(func):
            raise TypeError(f"{spec['function']} isn't a function")
    except BaseException as err:  # the solution may raise anything, even SystemExit
        payload["load_error"] = "".join(traceback.format_exception_only(err)).strip()[-1500:]
        _write(results_path, payload)
        return

    for case in spec["tests"]:
        args = copy.deepcopy(case["args"])
        result = {"passed": False, "got": None, "error": None}
        try:
            got = _normalise(func(*args))
            expected = case["expected"]
            if spec["compare"] == "unordered" and isinstance(got, list):
                got = sorted(got, key=_key)
                expected = sorted(expected, key=_key)
            result["passed"] = _equal(got, expected, spec.get("tolerance"))
            result["got"] = _shown(got)
        except BaseException as err:
            result["error"] = f"{type(err).__name__}: {err}"[:MAX_SHOWN]
        payload["cases"].append(result)
        _write(results_path, payload)


if __name__ == "__main__":
    main()
