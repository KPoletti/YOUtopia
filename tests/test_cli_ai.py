import json
from datetime import date

import httpx
import keyring
import pytest
from keyring.backends import fail
from typer.testing import CliRunner

from youtopia import cli, config, db, secrets
from youtopia.cli import app
from youtopia.models import Domain
from youtopia.providers import registry

runner = CliRunner()
KEY = "sk-live-NEVER-SHOW-0123456789wxyz"

GOOD_TASKS = {
    "tasks": [
        {
            "title": f"Fresh idea {i}",
            "domain": domain,
            "difficulty": 2,
            "duration_minutes": 10,
            "instructions": "Do a small, specific, safe thing for ten minutes.",
            "done_criteria": "It is done.",
            "requires": [],
        }
        for i, domain in enumerate([d.value for d in Domain])
    ]
}


@pytest.fixture
def initialised(monkeypatch):
    monkeypatch.setattr(cli, "_today", lambda: date(2026, 10, 13))
    result = runner.invoke(
        app,
        ["init", "--interests", "all", "--minutes", "30", "--accessibility", "none",
         "--challenge", "2"],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def mock_openai(monkeypatch, handler):
    """Route the real OpenAI-compatible adapter through an in-memory transport."""
    real = registry.build_provider

    def build(settings, **kwargs):
        return real(settings, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(registry, "build_provider", build)


def use_openai():
    for key, value in [("ai.provider", "openai"), ("ai.model", "gpt-x"), ("ai.enabled", "true")]:
        assert runner.invoke(app, ["config", "set", key, value]).exit_code == 0


# --- config ----------------------------------------------------------------------


def test_config_show_and_set():
    result = runner.invoke(app, ["config", "set", "ai.timeout_s", "30"])
    assert result.exit_code == 0, result.output
    shown = runner.invoke(app, ["config", "show"])
    assert "ai.timeout_s" in shown.output and "30" in shown.output


def test_config_set_rejects_unknown_and_insecure():
    assert runner.invoke(app, ["config", "set", "ai.api_key", KEY]).exit_code == 2
    result = runner.invoke(app, ["config", "set", "ai.base_url", "http://example.com"])
    assert result.exit_code == 2
    assert "HTTPS" in result.output


# --- auth ------------------------------------------------------------------------


def test_auth_set_status_remove(memory_keyring):
    result = runner.invoke(app, ["auth", "set", "openai"], input=f"{KEY}\n")
    assert result.exit_code == 0, result.output
    assert memory_keyring.store[("youtopia", "openai")] == KEY
    assert "••••wxyz" in result.output

    status = runner.invoke(app, ["auth", "status"])
    assert "openai" in status.output and "••••wxyz" in status.output
    assert "keyring" in status.output

    removed = runner.invoke(app, ["auth", "remove", "openai"])
    assert removed.exit_code == 0
    assert ("youtopia", "openai") not in memory_keyring.store
    for output in (result.output, status.output, removed.output):
        assert KEY not in output


def test_auth_status_shows_env_source(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    status = runner.invoke(app, ["auth", "status"])
    assert "env ANTHROPIC_API_KEY" in status.output
    assert KEY not in status.output


def test_auth_set_without_keyring_explains_env_vars():
    keyring.set_keyring(fail.Keyring())
    result = runner.invoke(app, ["auth", "set", "anthropic"], input=f"{KEY}\n")
    assert result.exit_code == 1
    assert "YOUTOPIA_API_KEY" in result.output and "ANTHROPIC_API_KEY" in result.output
    assert KEY not in result.output


def test_auth_unknown_provider():
    assert runner.invoke(app, ["auth", "set", "skynet"]).exit_code == 2


# --- ai test ---------------------------------------------------------------------


def test_ai_test_reports_provider_model_and_time(monkeypatch):
    use_openai()
    secrets.set_key("openai", KEY)
    mock_openai(
        monkeypatch,
        lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "ready"}}]}),
    )
    result = runner.invoke(app, ["ai", "test"])
    assert result.exit_code == 0, result.output
    assert "openai" in result.output and "gpt-x" in result.output and " ms" in result.output
    assert KEY not in result.output


def test_ai_test_without_key_fails_kindly():
    use_openai()
    result = runner.invoke(app, ["ai", "test"])
    assert result.exit_code == 1
    assert "youtopia auth set openai" in result.output


# --- the key never leaks -----------------------------------------------------------


def test_key_never_reaches_output_config_or_db(initialised, monkeypatch):
    outputs = [runner.invoke(app, ["auth", "set", "openai"], input=f"{KEY}\n").output]
    use_openai()
    seen_auth = []

    def handler(request):
        seen_auth.append(request.headers["authorization"])
        body = json.loads(request.content)
        assert KEY not in json.dumps(body)  # the key only travels in the header
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(GOOD_TASKS)}}]}
        )

    mock_openai(monkeypatch, handler)
    for command in (["today"], ["swap", "1"], ["done", "2"], ["stats"], ["config", "show"],
                    ["auth", "status"], ["ai", "test"]):  # fmt: skip
        result = runner.invoke(app, command)
        assert result.exit_code == 0, (command, result.output)
        outputs.append(result.output)

    # A provider error that echoes the key back is redacted too.
    mock_openai(monkeypatch, lambda r: httpx.Response(401, text=f"bad key {KEY}"))
    outputs.append(runner.invoke(app, ["ai", "test"]).output)

    assert seen_auth and all(h == f"Bearer {KEY}" for h in seen_auth)
    assert "Fresh idea" in outputs[1]  # AI tasks really were used
    for output in outputs:
        assert KEY not in output
        assert KEY[-8:] not in output  # nothing beyond the last four characters
    assert KEY not in config.config_path().read_text()
    db_bytes = db.db_path().read_bytes()
    assert KEY.encode() not in db_bytes


# --- rendering, greeting, more -------------------------------------------------------


def test_ai_text_renders_inertly(initialised, monkeypatch):
    use_openai()
    secrets.set_key("openai", KEY)
    nasty = dict(GOOD_TASKS)
    nasty["tasks"] = [
        t | {"title": "[bold red]Shouty[/bold red] \x1b]52;c;ZXZpbA==\x07title"}
        for t in GOOD_TASKS["tasks"]
    ]
    mock_openai(
        monkeypatch,
        lambda r: httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(nasty)}}]}
        ),
    )
    result = runner.invoke(app, ["today"])
    assert result.exit_code == 0, result.output
    assert "[bold red]Shouty[/bold red]" in result.output  # shown literally, not styled
    assert "\x1b" not in result.output and "\x07" not in result.output


def test_today_greets_and_done_encourages(initialised):
    from youtopia import encouragement

    bank = encouragement.phrase_bank()
    greetings = {p for phrases in bank["greeting"].values() for p in phrases}
    result = runner.invoke(app, ["today", "--offline"])
    flat = " ".join(result.output.split())  # long greetings wrap at the test terminal width
    assert any(flat.startswith(" ".join(g.split())) for g in greetings)

    done = runner.invoke(app, ["done", "1"])
    assert done.exit_code == 0, done.output
    assert "Nice work." not in done.output  # the old placeholder is gone


def test_more_command(initialised):
    assert runner.invoke(app, ["today"]).exit_code == 0
    result = runner.invoke(app, ["more", "2"])
    assert result.exit_code == 0, result.output
    assert "4. " in result.output and "5. " in result.output
    assert runner.invoke(app, ["more", "0"]).exit_code == 2
    assert runner.invoke(app, ["done", "5"]).exit_code == 0
