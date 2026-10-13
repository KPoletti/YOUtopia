"""Settings in ~/.youtopia/config.toml. Never holds API keys (see secrets.py)."""

import json
import os
import tomllib
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path

from youtopia.db import data_dir
from youtopia.providers.base import ProviderError, check_url
from youtopia.providers.catalog import PROVIDERS, provider_names

CONFIG_FILENAME = "config.toml"
MAX_TIMEOUT_S = 300
MAX_CALLS_PER_DAY = 1000


class ConfigError(ValueError):
    """Invalid config file or value. The message is shown to the user."""


@dataclass(frozen=True)
class AISettings:
    enabled: bool = False
    provider: str = "anthropic"
    model: str = ""  # empty: the provider's default model, if it has one
    base_url: str = ""  # empty: the provider's ready-made URL
    timeout_s: int = 20
    max_calls_per_day: int = 20
    reword_encouragement: bool = False


@dataclass(frozen=True)
class Config:
    ai: AISettings = AISettings()


def config_path() -> Path:
    return data_dir() / CONFIG_FILENAME


def keys() -> list[str]:
    return [f"ai.{f.name}" for f in fields(AISettings)]


def load_config(path: Path | None = None) -> Config:
    path = path or config_path()
    if not path.exists():
        return Config()
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as err:
        raise ConfigError(f"{path} isn't valid TOML: {err}") from None
    ai = raw.get("ai", {})
    if not isinstance(ai, dict):
        raise ConfigError("[ai] must be a table.")
    settings = AISettings()
    for name, value in ai.items():
        settings = _with(settings, name, value)
    return Config(ai=settings)


def set_value(key: str, raw: str, path: Path | None = None) -> Config:
    """Parse, validate and save one setting, e.g. set_value("ai.timeout_s", "30")."""
    section, _, name = key.partition(".")
    if section != "ai" or name not in {f.name for f in fields(AISettings)}:
        raise ConfigError(f"Unknown setting {key!r}. Choose from: {', '.join(keys())}.")
    current = load_config(path)
    config = Config(ai=_with(current.ai, name, _parse(name, raw)))
    save_config(config, path)
    return config


def save_config(config: Config, path: Path | None = None) -> None:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["[ai]"] + [f"{name} = {_toml_value(v)}" for name, v in asdict(config.ai).items()]
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _parse(name: str, raw: str) -> object:
    kind = type(getattr(AISettings(), name))
    raw = raw.strip()
    if kind is bool:
        lowered = raw.lower()
        if lowered in {"true", "yes", "on", "1"}:
            return True
        if lowered in {"false", "no", "off", "0"}:
            return False
        raise ConfigError(f"ai.{name} must be true or false.")
    if kind is int:
        try:
            return int(raw)
        except ValueError:
            raise ConfigError(f"ai.{name} must be a whole number.") from None
    return raw


def _with(settings: AISettings, name: str, value: object) -> AISettings:
    """Return settings with one field changed, after validating it."""
    if name not in {f.name for f in fields(AISettings)}:
        raise ConfigError(f"Unknown setting 'ai.{name}'. Choose from: {', '.join(keys())}.")
    expected = type(getattr(AISettings(), name))
    if type(value) is not expected:
        raise ConfigError(f"ai.{name} must be a {expected.__name__}.")
    if isinstance(value, str) and any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ConfigError(f"ai.{name} can't contain control characters.")
    if name == "provider" and value not in PROVIDERS:
        names = ", ".join(provider_names())
        raise ConfigError(f"Unknown provider {value!r}. Choose from: {names}.")
    if name == "base_url" and value:
        try:
            value = check_url(str(value))
        except ProviderError as err:
            raise ConfigError(str(err)) from None
    if name == "timeout_s" and not 1 <= value <= MAX_TIMEOUT_S:
        raise ConfigError(f"ai.timeout_s must be between 1 and {MAX_TIMEOUT_S}.")
    if name == "max_calls_per_day" and not 0 <= value <= MAX_CALLS_PER_DAY:
        raise ConfigError(f"ai.max_calls_per_day must be between 0 and {MAX_CALLS_PER_DAY}.")
    return replace(settings, **{name: value})


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    # JSON string escapes are a subset of TOML basic-string escapes.
    return json.dumps(str(value), ensure_ascii=False)
