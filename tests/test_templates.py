"""Every built-in problem is well formed, and its hidden tests pass with the reference."""

from pathlib import Path

import pytest

from tests import reference_solutions
from youtopia import generator, judge
from youtopia.models import MAX_LEVEL, MIN_LEVEL, Domain

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = generator.load_templates()


@pytest.fixture(scope="module")
def reference_file(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("reference") / "reference.py"
    path.write_text(
        f"import sys\nsys.path.insert(0, {str(ROOT)!r})\n"
        "from tests.reference_solutions import *  # noqa: F403\n"
    )
    return path


def test_every_template_is_a_problem_with_a_reference():
    for t in TEMPLATES:
        assert t.problem is not None, t.title
        assert hasattr(reference_solutions, t.problem.function), t.problem.function
        assert len(t.problem.tests) >= 5, t.title
        assert "Example 1:" in t.instructions and "Constraints:" in t.instructions, t.title


def test_two_problems_per_area_and_level():
    for domain in Domain:
        for level in range(MIN_LEVEL, MAX_LEVEL + 1):
            count = sum(1 for t in TEMPLATES if t.domain == domain and t.difficulty == level)
            assert count == 2, (domain, level)


def test_function_names_are_unique():
    names = [t.problem.function for t in TEMPLATES]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda t: t.problem.function)
def test_reference_passes_every_hidden_test(template, reference_file):
    verdict = judge.run_tests(reference_file, template.problem)
    assert verdict.load_error is None, verdict.load_error
    failure = verdict.first_failure
    assert verdict.accepted, (failure.number, failure.args, failure.got, failure.error)
