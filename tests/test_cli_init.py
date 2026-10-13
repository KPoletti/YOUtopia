from typer.testing import CliRunner

from youtopia.cli import app
from youtopia.db import session_scope
from youtopia.models import DEFAULT_TONE, ToneMix
from youtopia.profile import get_profile

runner = CliRunner()

FLAGS = [
    "init",
    "--interests", "creative,social",
    "--minutes", "15",
    "--accessibility", "none",
    "--challenge", "2",
]  # fmt: skip


def stored_profile():
    with session_scope() as session:
        profile = get_profile(session)
        if profile is not None:
            session.expunge(profile)
        return profile


def test_init_with_flags():
    result = runner.invoke(app, [*FLAGS, "--sarcasm", "3", "--rudeness", "2"])
    assert result.exit_code == 0, result.output

    profile = stored_profile()
    assert profile.interests == ["creative", "social"]
    assert profile.minutes_per_day == 15
    assert profile.accessibility_limits == []
    # Unspecified sliders keep their defaults.
    assert profile.tone == ToneMix(
        sincerity=DEFAULT_TONE.sincerity, humor=DEFAULT_TONE.humor, sarcasm=3, rudeness=2
    )


def test_init_interactive_reprompts_on_bad_input():
    answers = [
        "creative, juggling",  # unknown interest -> asked again
        "all",
        "abc",  # not a number -> asked again
        "30",
        "no stairs",
        "9",  # out of range -> asked again
        "4",
        "",  # keep default tone
    ]
    result = runner.invoke(app, ["init"], input="\n".join(answers) + "\n")
    assert result.exit_code == 0, result.output
    assert "Unknown interest" in result.output

    profile = stored_profile()
    assert len(profile.interests) == 6
    assert profile.minutes_per_day == 30
    assert profile.accessibility_limits == ["no stairs"]
    assert profile.preferred_challenge == 4
    assert profile.tone == DEFAULT_TONE


def test_init_interactive_custom_tone():
    answers = ["all", "20", "none", "2", "y", "2", "5", "7", "4", "1"]  # 7 -> asked again
    result = runner.invoke(app, ["init"], input="\n".join(answers) + "\n")
    assert result.exit_code == 0, result.output
    assert stored_profile().tone == ToneMix(sincerity=2, humor=5, sarcasm=4, rudeness=1)


def test_init_rejects_bad_tone_flag():
    result = runner.invoke(app, [*FLAGS, "--rudeness", "6"])
    assert result.exit_code == 2
    assert stored_profile() is None


def test_reinit_asks_before_overwriting():
    runner.invoke(app, [*FLAGS, "--sarcasm", "5"])

    declined = runner.invoke(app, [*FLAGS, "--sarcasm", "0"], input="n\n")
    assert declined.exit_code != 0
    assert stored_profile().sarcasm == 5

    accepted = runner.invoke(app, [*FLAGS, "--sarcasm", "0", "--yes"])
    assert accepted.exit_code == 0, accepted.output
    assert stored_profile().sarcasm == 0
