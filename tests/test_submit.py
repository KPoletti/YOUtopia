import random
from datetime import date
from pathlib import Path

import pytest
from sqlmodel import select
from typer.testing import CliRunner

from youtopia import cli, daily, stats
from youtopia import profile as profiles
from youtopia.cli import app
from youtopia.models import Domain, SkillLevel, Submission, TaskStatus

ROOT = Path(__file__).resolve().parents[1]
DAY = date(2026, 10, 13)
runner = CliRunner()


def reference(tmp_path) -> Path:
    path = tmp_path / "solution.py"
    path.write_text(
        f"import sys\nsys.path.insert(0, {str(ROOT)!r})\n"
        "from tests.reference_solutions import *  # noqa: F403\n"
    )
    return path


def wrong(tmp_path, task) -> Path:
    path = tmp_path / "wrong.py"
    path.write_text(f"def {task.problem['function']}(*args):\n    return 'nope'\n")
    return path


@pytest.fixture
def profile(session):
    data = profiles.ProfileInput(interests=list(Domain), minutes_per_day=60, preferred_challenge=2)
    return profiles.save_profile(session, data)


@pytest.fixture
def tasks(session, profile):
    return daily.ensure_today(session, profile, DAY, random.Random(0))


def test_every_offered_task_has_a_problem(tasks):
    assert all(t.problem and t.problem["tests"] for t in tasks)


def test_accepted_submission_completes_the_task(session, tasks, tmp_path):
    result = daily.submit_task(session, DAY, 1, reference(tmp_path))
    assert result.verdict.accepted
    assert result.completion is not None
    assert result.task.status == TaskStatus.DONE
    sub = session.exec(select(Submission)).one()
    assert (sub.passed, sub.total, sub.accepted) == (result.verdict.total,) * 2 + (True,)
    skill = session.exec(select(SkillLevel).where(SkillLevel.domain == tasks[0].domain)).one()
    assert skill.recent_successes == 1


def test_failed_submission_is_recorded_without_penalty(session, tasks, tmp_path):
    before = session.exec(select(SkillLevel)).all()
    levels = {s.domain: (s.level, s.recent_successes) for s in before}
    result = daily.submit_task(session, DAY, 2, wrong(tmp_path, tasks[1]))
    assert not result.verdict.accepted
    assert result.completion is None
    assert tasks[1].status == TaskStatus.OFFERED
    assert session.exec(select(Submission)).one().passed == 0
    after = {s.domain: (s.level, s.recent_successes) for s in session.exec(select(SkillLevel))}
    assert after == levels


def test_resubmitting_a_solved_task_doesnt_complete_it_twice(session, tasks, tmp_path):
    daily.submit_task(session, DAY, 1, reference(tmp_path))
    again = daily.submit_task(session, DAY, 1, reference(tmp_path))
    assert again.verdict.accepted and again.completion is None
    assert len(session.exec(select(Submission)).all()) == 2


def test_stats_show_scores(session, tasks, tmp_path):
    daily.submit_task(session, DAY, 1, wrong(tmp_path, tasks[0]))
    daily.submit_task(session, DAY, 1, reference(tmp_path))
    result = stats.compute_stats(session, DAY)
    total = len(tasks[0].problem["tests"])
    assert result.history[0].score == f"{total}/{total}"
    assert result.solved_by_tests == 1


def test_tasks_without_tests_point_to_done(session, tasks):
    tasks[0].problem = None
    session.add(tasks[0])
    with pytest.raises(daily.DailyError, match="youtopia done 1"):
        daily.submit_task(session, DAY, 1, Path("x.py"))


# --- CLI ---------------------------------------------------------------------------


@pytest.fixture
def initialised(monkeypatch):
    monkeypatch.setattr(cli, "_today", lambda: DAY)
    result = runner.invoke(
        app,
        ["init", "--interests", "all", "--minutes", "60", "--accessibility", "none",
         "--challenge", "2"],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert runner.invoke(app, ["today", "--offline"]).exit_code == 0


def test_today_shows_the_signature(initialised):
    result = runner.invoke(app, ["today", "--offline"])
    assert "Write:" in result.output and "def " in result.output
    assert "youtopia submit" in result.output


def test_starter_then_submit(initialised, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["starter", "1"])
    assert result.exit_code == 0, result.output
    skeleton = (tmp_path / "task_1.py").read_text()
    assert "raise NotImplementedError" in skeleton
    assert runner.invoke(app, ["starter", "1"]).exit_code == 1  # never overwrites

    failing = runner.invoke(app, ["submit", "1", "task_1.py"])
    assert failing.exit_code == 0, failing.output
    assert "First failing test" in failing.output and "NotImplementedError" in failing.output

    reference(tmp_path)
    passing = runner.invoke(app, ["submit", "1", "solution.py"])
    assert passing.exit_code == 0, passing.output
    assert "Accepted" in passing.output and "done." in passing.output

    shown = runner.invoke(app, ["stats"])
    assert "solved with every hidden test passing" in shown.output


def test_submit_errors(initialised, tmp_path):
    assert runner.invoke(app, ["submit", "1", str(tmp_path / "nope.py")]).exit_code == 1
    assert runner.invoke(app, ["submit", "9", str(tmp_path / "nope.py")]).exit_code == 1
