import stat
import tomllib

import pytest

from youtopia import config


def test_defaults_when_no_file():
    settings = config.load_config().ai
    assert settings == config.AISettings()
    assert (settings.enabled, settings.timeout_s, settings.max_calls_per_day) == (False, 20, 20)


def test_set_round_trips_through_toml():
    config.set_value("ai.enabled", "yes")
    config.set_value("ai.provider", "ollama")
    config.set_value("ai.model", 'llama "3.2" \\ test')
    config.set_value("ai.timeout_s", "45")
    settings = config.load_config().ai
    assert settings.enabled is True
    assert settings.provider == "ollama"
    assert settings.model == 'llama "3.2" \\ test'
    assert settings.timeout_s == 45
    tomllib.loads(config.config_path().read_text())  # still valid TOML


def test_config_file_is_private():
    config.set_value("ai.enabled", "true")
    assert stat.S_IMODE(config.config_path().stat().st_mode) == 0o600


@pytest.mark.parametrize(
    "key, value, message",
    [
        ("ai.api_key", "sk-123", "Unknown setting"),
        ("model", "x", "Unknown setting"),
        ("ai.provider", "skynet", "Unknown provider"),
        ("ai.enabled", "maybe", "true or false"),
        ("ai.timeout_s", "soon", "whole number"),
        ("ai.timeout_s", "0", "between 1"),
        ("ai.max_calls_per_day", "-1", "between 0"),
        ("ai.base_url", "http://example.com/v1", "HTTPS"),
        ("ai.base_url", "https://user:pw@example.com", "credentials"),
        ("ai.model", "bad\x7fname", "control characters"),
    ],
)
def test_bad_values_are_rejected(key, value, message):
    with pytest.raises(config.ConfigError, match=message):
        config.set_value(key, value)
    assert not config.config_path().exists()


@pytest.mark.parametrize("url", ["http://localhost:11434/v1", "http://127.0.0.1:1234/v1"])
def test_plain_http_is_fine_for_localhost(url):
    assert config.set_value("ai.base_url", url).ai.base_url == url


def test_broken_file_gives_a_clear_error():
    config.config_path().parent.mkdir(parents=True)
    config.config_path().write_text("[ai\nenabled = ")
    with pytest.raises(config.ConfigError, match="isn't valid TOML"):
        config.load_config()


def test_unknown_keys_in_file_are_rejected():
    config.config_path().parent.mkdir(parents=True)
    config.config_path().write_text('[ai]\napi_key = "sk-oops"\n')
    with pytest.raises(config.ConfigError, match="Unknown setting"):
        config.load_config()
