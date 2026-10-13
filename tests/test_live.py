"""Optional live tests against your real provider. Run with YOUTOPIA_LIVE_TESTS=1, using the
key and settings from your environment and ~/.youtopia/config.toml. Each run spends a call."""

import os
import random
from datetime import date

import pytest

from youtopia import config, daily, generator
from youtopia import profile as profiles
from youtopia.models import Domain, TaskSource
from youtopia.providers.registry import build_provider

pytestmark = pytest.mark.skipif(
    os.environ.get("YOUTOPIA_LIVE_TESTS") != "1", reason="set YOUTOPIA_LIVE_TESTS=1 to run"
)


@pytest.fixture
def settings(monkeypatch):
    real_home = os.path.expanduser("~/.youtopia")
    real = config.load_config(config.Path(real_home) / config.CONFIG_FILENAME).ai
    return config.AISettings(**{**vars(real), "enabled": True})


def test_live_provider_answers(settings):
    reply = build_provider(settings).complete(
        "You are a connectivity check.", "Reply with the single word: ready", max_tokens=1000
    )
    assert reply.strip()


def test_live_generation_produces_valid_tasks(session, settings):
    profile = profiles.save_profile(
        session, profiles.ProfileInput(interests=list(Domain), minutes_per_day=30)
    )
    ai = generator.AISource(settings, build_provider)
    result = daily.offer_today(session, profile, date.today(), random.Random(0), ai=ai)
    assert len(result.tasks) == daily.DAILY_SET_SIZE
    assert any(t.source == TaskSource.AI for t in result.tasks), result.notice
