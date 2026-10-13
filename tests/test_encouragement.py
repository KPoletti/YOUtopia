import random
from collections import Counter
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlmodel import select

from youtopia import daily, encouragement, safety
from youtopia import profile as profiles
from youtopia.encouragement import BLEND_TRAITS, GUILT_PHRASES, GUILT_WEIGHT, PERSONAL_JABS
from youtopia.generator import AISource
from youtopia.models import SINCERE_FALLBACK_TONE, Completion, Domain, ToneMix
from youtopia.providers.base import ProviderError
from youtopia.providers.fake import FakeProvider

DAY = date(2026, 10, 13)
TEASING_TONE = ToneMix(sincerity=1, humor=1, sarcasm=4, rudeness=4)


# --- phrase bank lint -----------------------------------------------------------


def all_phrases():
    for kind, traits in encouragement.phrase_bank().items():
        for trait, phrases in traits.items():
            for phrase in phrases:
                yield kind, trait, phrase


def test_every_kind_and_trait_has_phrases():
    bank = encouragement.phrase_bank()
    for kind in ("done", "greeting"):
        for trait in BLEND_TRAITS:
            assert len(bank[kind][trait]) >= 2, (kind, trait)


@pytest.mark.parametrize("kind, trait, phrase", list(all_phrases()))
def test_phrase_rules(kind, trait, phrase):
    lowered = phrase.lower()
    if trait != "guilt":
        assert not [p for p in GUILT_PHRASES if p in lowered]
    assert not safety.risky_themes([phrase])
    if trait in ("sarcasm", "rudeness"):
        assert "{task}" in phrase or "task" in lowered, "tease the task, not the person"
    if trait in ("sarcasm", "rudeness", "guilt"):
        assert not [p for p in PERSONAL_JABS if p in lowered], "never insult the person"
    assert encouragement.acceptable_text(phrase.replace("{task}", "Tidy a drawer"), trait)
    if kind == "greeting":
        assert "{task}" not in phrase


# --- weighted blend ----------------------------------------------------------------


@pytest.mark.parametrize("tone", [ToneMix(4, 1, 0, 0), ToneMix(1, 2, 3, 4), ToneMix(0, 0, 5, 0)])
def test_trait_frequencies_follow_slider_weights(tone):
    rng = random.Random(42)
    draws = 20_000
    counts = Counter(encouragement.pick_trait(tone, rng) for _ in range(draws))
    weights = tone.as_dict() | {"guilt": GUILT_WEIGHT}
    total = sum(weights.values())
    for trait, weight in weights.items():
        assert counts[trait] / draws == pytest.approx(weight / total, abs=0.015), trait


def test_every_user_gets_some_guilt():
    for tone in (ToneMix(), ToneMix(5, 0, 0, 0), ToneMix(0, 0, 0, 0)):
        assert encouragement.blend_weights(tone)["guilt"] == GUILT_WEIGHT


def test_all_zero_sliders_mean_sincere_plus_guilt():
    weights = encouragement.blend_weights(ToneMix(0, 0, 0, 0))
    assert {t for t, w in weights.items() if w} == {"sincerity", "guilt"}


def test_compose_fills_in_the_task():
    message = encouragement.compose(
        "done", ToneMix(0, 0, 0, 5), random.Random(3), "Tidy a drawer", guilt=0
    )
    assert message.trait == "rudeness"
    assert "{task}" not in message.text


# --- sincere fallback ----------------------------------------------------------------


@pytest.fixture
def profile(session):
    data = profiles.ProfileInput(
        interests=list(Domain), minutes_per_day=60, preferred_challenge=2, tone=TEASING_TONE
    )
    saved = profiles.save_profile(session, data)
    saved.created_at = datetime(2026, 10, 1, 9, tzinfo=UTC)
    session.add(saved)
    return saved


def complete_on(session, profile, day, slot=1):
    daily.offer_today(session, profile, day, random.Random(0))
    result = daily.complete_task(session, day, slot)
    completion = session.exec(select(Completion).where(Completion.task_id == result.task.id)).one()
    completion.completed_at = datetime.combine(day, datetime.min.time(), UTC) + timedelta(hours=12)
    session.add(completion)
    session.flush()
    return result.task


def test_missed_days_trigger_the_soft_landing(session, profile):
    complete_on(session, profile, DAY)
    gap = encouragement.FALLBACK_AFTER_MISSED_DAYS
    assert not encouragement.soft_landing(session, profile, DAY + timedelta(days=gap))
    assert encouragement.soft_landing(session, profile, DAY + timedelta(days=gap + 1))
    assert (
        encouragement.current_tone(session, profile, DAY + timedelta(days=gap + 1))
        == SINCERE_FALLBACK_TONE
    )


def test_new_profile_counts_from_its_creation(session, profile):
    assert not encouragement.soft_landing(session, profile, date(2026, 10, 2))
    assert encouragement.soft_landing(session, profile, date(2026, 10, 10))


def test_declines_in_a_row_trigger_it_and_a_completion_clears_it(session, profile):
    complete_on(session, profile, DAY - timedelta(days=1))
    daily.offer_today(session, profile, DAY, random.Random(0))
    for _ in range(encouragement.FALLBACK_AFTER_DECLINES):
        daily.swap_task(session, profile, DAY, 1, random.Random(0))
    assert encouragement.soft_landing(session, profile, DAY)

    task = daily.complete_task(session, DAY, 2).task
    # The message for the completion that ends the slump is still the gentle one...
    assert (
        encouragement.current_tone(session, profile, DAY, exclude_task_id=task.id)
        == SINCERE_FALLBACK_TONE
    )
    # ...and from then on the usual blend is back. The sliders never changed.
    assert encouragement.current_tone(session, profile, DAY) == TEASING_TONE
    assert profile.tone == TEASING_TONE


def test_soft_landing_messages_are_sincere_only_no_guilt(session, profile):
    later = DAY + timedelta(days=30)
    sincere = set(encouragement.phrase_bank()["greeting"]["sincerity"])
    for seed in range(40):
        text = encouragement.greeting(session, profile, later, random.Random(seed))
        assert text in sincere


def test_guilt_shows_up_outside_the_soft_landing(session, profile):
    complete_on(session, profile, DAY)
    guilt = set(encouragement.phrase_bank()["greeting"]["guilt"])
    texts = {encouragement.greeting(session, profile, DAY, random.Random(s)) for s in range(60)}
    assert texts & guilt


# --- AI rewording --------------------------------------------------------------------


def reword_source(*responses, enabled=True, cap=20):
    provider = FakeProvider(responses)
    ai = AISource.from_provider(provider, reword_encouragement=enabled, max_calls_per_day=cap)
    return provider, ai


@pytest.fixture
def done_task(session, profile):
    return complete_on(session, profile, DAY)


def test_reworded_message_is_used(session, profile, done_task):
    provider, ai = reword_source('"Splendid. That task is history."')
    text = encouragement.done_message(session, profile, done_task, DAY, random.Random(0), ai)
    assert text == "Splendid. That task is history."
    assert "<<<DATA" in provider.calls[0].user


@pytest.mark.parametrize(
    "reply",
    [
        "You failed yesterday but okay.",  # guilt
        "Wow, you're so lazy, but fine.",  # personal jab (when teasing)
        "Celebrate with a glass of wine!",  # unsafe
        "x" * 300,  # too long
        "",
        ProviderError("timeout"),
        RuntimeError("boom"),
    ],
)
def test_bad_rewording_keeps_the_phrase_bank_message(session, profile, done_task, reply):
    _, ai = reword_source(reply)
    rng_seed = 5
    expected = encouragement.done_message(
        session, profile, done_task, DAY, random.Random(rng_seed), None
    )
    text = encouragement.done_message(session, profile, done_task, DAY, random.Random(rng_seed), ai)
    assert text == expected


def test_rewording_strips_escapes(session, profile, done_task):
    _, ai = reword_source("\x1b[31mNicely\x1b[0m done.\x07")
    assert encouragement.done_message(session, profile, done_task, DAY, None, ai) == "Nicely done."


def test_rewording_is_off_by_default_and_respects_the_cap(session, profile, done_task):
    provider, ai = reword_source("Unused.", enabled=False)
    encouragement.done_message(session, profile, done_task, DAY, None, ai)
    assert provider.calls == []

    provider, ai = reword_source("One.", "Two.", cap=1)
    encouragement.done_message(session, profile, done_task, DAY, None, ai)
    encouragement.done_message(session, profile, done_task, DAY, None, ai)
    assert len(provider.calls) == 1


def test_guilt_wording_only_passes_for_the_guilt_trait():
    text = "Those tasks waited all day and you missed them."
    assert encouragement.acceptable_text(text, "guilt")
    assert not encouragement.acceptable_text(text, "sincerity")
    assert not encouragement.acceptable_text("Wow, you're so lazy.", "guilt")
