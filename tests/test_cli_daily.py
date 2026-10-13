from datetime import date

import pytest
from typer.testing import CliRunner

from youtopia import cli
from youtopia.cli import app

runner = CliRunner()


@pytest.fixture
def initialised(monkeypatch):
    monkeypatch.setattr(cli, "_today", lambda: date(2026, 10, 13))
    result = runner.invoke(
        app,
        ["init", "--interests", "all", "--minutes", "30", "--accessibility", "none",
         "--challenge", "2"],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize("command", [["today"], ["swap", "1"], ["done", "1"], ["stats"]])
def test_commands_need_a_profile(command):
    result = runner.invoke(app, command)
    assert result.exit_code == 1
    assert "youtopia init" in result.output


def test_daily_loop(initialised):
    today = runner.invoke(app, ["today"])
    assert today.exit_code == 0, today.output
    for n in ("1.", "2.", "3."):
        assert n in today.output

    swapped = runner.invoke(app, ["swap", "2"])
    assert swapped.exit_code == 0, swapped.output
    assert "another option" in swapped.output

    done = runner.invoke(app, ["done", "1", "--note", "fun"])
    assert done.exit_code == 0, done.output
    assert "done" in done.output

    again = runner.invoke(app, ["done", "1"])
    assert again.exit_code == 1
    assert "already" in again.output

    shown = runner.invoke(app, ["stats"])
    assert shown.exit_code == 0, shown.output
    assert "1 task done" in shown.output
    assert "First task done" in shown.output
    assert "fun" in shown.output


def test_swap_unknown_task(initialised):
    runner.invoke(app, ["today"])
    result = runner.invoke(app, ["swap", "9"])
    assert result.exit_code == 1
    assert "no task 9" in result.output
