import socket
from datetime import date

import pytest
from sqlmodel import select
from typer.testing import CliRunner

from youtopia import cli, difficulty
from youtopia.cli import app
from youtopia.db import session_scope
from youtopia.encouragement import GUILT_PHRASES
from youtopia.models import Domain, SkillLevel, Task
from youtopia.profile import get_profile

runner = CliRunner()


@pytest.fixture
def initialised(monkeypatch):
    monkeypatch.setattr(cli, "_today", lambda: date(2026, 10, 13))
    result = runner.invoke(
        app,
        ["init", "--interests", "production,training", "--minutes", "30", "--accessibility",
         "none", "--challenge", "2", "--humor", "3"],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def stored():
    with session_scope() as session:
        return get_profile(session).model_copy()


def test_profile_needs_a_profile():
    result = runner.invoke(app, ["profile"])
    assert result.exit_code == 1
    assert "youtopia init" in result.output


def test_profile_shows_answers_and_tone(initialised):
    result = runner.invoke(app, ["profile"])
    assert result.exit_code == 0, result.output
    assert "production, training" in result.output
    assert "Humor" in result.output and "■■■□□ 3" in result.output


def test_edit_one_field_keeps_the_rest_and_progress(initialised):
    with session_scope() as session:
        skill = session.get(SkillLevel, 1)
        skill.level, skill.recent_successes = 4, 2
        session.add(skill)

    result = runner.invoke(app, ["profile", "--edit", "minutes"], input="45\n")
    assert result.exit_code == 0, result.output
    profile = stored()
    assert profile.minutes_per_day == 45
    assert profile.interests == ["production", "training"]
    assert profile.humor == 3
    with session_scope() as session:
        assert session.get(SkillLevel, 1).level == 4


def test_edit_tone_reprompts_bad_values(initialised):
    result = runner.invoke(app, ["profile", "--edit", "tone"], input="5\n9\n0\n2\n1\n")
    assert result.exit_code == 0, result.output
    assert "between 0 and 5" in result.output
    assert stored().tone.as_dict() == {"sincerity": 5, "humor": 0, "sarcasm": 2, "rudeness": 1}


def test_edit_everything_with_current_answers_as_defaults(initialised):
    result = runner.invoke(app, ["profile", "--edit"], input="all\n\nno stairs\n4\n\n\n\n\n")
    assert result.exit_code == 0, result.output
    profile = stored()
    assert profile.interests == [d.value for d in Domain]
    assert profile.minutes_per_day == 30
    assert profile.accessibility_limits == ["no stairs"]
    assert profile.preferred_challenge == 4
    assert profile.humor == 3


@pytest.mark.parametrize(
    "args, message", [(["--edit", "colour"], "Unknown field"), (["minutes"], "--edit minutes")]
)
def test_bad_edit_requests(initialised, args, message):
    result = runner.invoke(app, ["profile", *args])
    assert result.exit_code == 2
    assert message in result.output


def test_help_now_works_offline_without_a_profile(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("help-now must not touch the network")

    monkeypatch.setattr(socket, "socket", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    result = runner.invoke(app, ["help-now"])
    assert result.exit_code == 0, result.output
    for expected in ("112", "911", "988", "116 123", "findahelpline.com"):
        assert expected in result.output


def test_level_changes_are_announced_kindly(initialised):
    assert runner.invoke(app, ["today"]).exit_code == 0
    with session_scope() as session:
        first = session.exec(select(Task).where(Task.slot == 1)).one()
        skill = session.exec(select(SkillLevel).where(SkillLevel.domain == first.domain)).one()
        skill.recent_declines = difficulty.EASE_AFTER_DECLINES - 1
        session.add(skill)

    result = runner.invoke(app, ["swap", "1"])
    assert result.exit_code == 0, result.output
    message = result.output.split("Swapped out")[0].lower()  # not the replacement task text
    assert "eased to level 1" in message
    assert not [p for p in GUILT_PHRASES if p in message]
