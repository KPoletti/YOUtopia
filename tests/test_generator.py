import random
from datetime import date

import pytest

from youtopia import generator
from youtopia.generator import History, TaskTemplate, TemplateError
from youtopia.models import MAX_LEVEL, MIN_LEVEL, Domain, Profile


def make_profile(**overrides) -> Profile:
    values = dict(
        interests=[d.value for d in Domain],
        minutes_per_day=30,
        accessibility_limits=[],
        preferred_challenge=2,
    )
    values.update(overrides)
    return Profile(**values)


def tpl(title, domain=Domain.CREATIVE, difficulty=2, minutes=10, requires=()) -> TaskTemplate:
    return TaskTemplate(
        title=title,
        instructions="Do it.",
        domain=domain,
        difficulty=difficulty,
        duration_minutes=minutes,
        done_criteria="Done.",
        requires=frozenset(requires),
    )


def pick(candidates, profile=None, levels=None, history=None, avoid=(), seed=0):
    return generator.pick_template(
        candidates,
        profile or make_profile(),
        levels or {},
        history or History(),
        set(avoid),
        random.Random(seed),
    )


def test_built_in_library_is_valid_and_covers_every_domain_and_level():
    templates = generator.load_templates()
    cells = {(t.domain, t.difficulty) for t in templates}
    for domain in Domain:
        for level in range(MIN_LEVEL, MAX_LEVEL + 1):
            assert (domain, level) in cells, f"no {domain} template at level {level}"


def test_short_tasks_exist_in_every_domain():
    templates = generator.load_templates()
    for domain in Domain:
        assert any(t.domain == domain and t.duration_minutes <= 10 for t in templates)


@pytest.mark.parametrize(
    "text",
    [
        "- title: X\n  domain: cooking\n  difficulty: 1\n  duration_minutes: 5\n"
        "  instructions: a\n  done_criteria: b\n",
        "- title: X\n  domain: creative\n  difficulty: 9\n  duration_minutes: 5\n"
        "  instructions: a\n  done_criteria: b\n",
        "- title: X\n  domain: creative\n  difficulty: 1\n  duration_minutes: 5\n"
        "  instructions: a\n  done_criteria: b\n  requires: [flying]\n",
        "- title: X\n  domain: creative\n  difficulty: 1\n  duration_minutes: 5\n",
    ],
)
def test_parse_templates_rejects_bad_entries(text):
    with pytest.raises(TemplateError):
        generator.parse_templates(text)


@pytest.mark.parametrize(
    ("limits", "blocked"),
    [
        (["no kneeling"], {"kneeling"}),
        (["Wheelchair user"], {"standing", "walking"}),
        (["low vision", "hard of hearing"], {"vision", "hearing"}),
        (["housebound"], {"going_out"}),
        ([], set()),
        (["none"], set()),
    ],
)
def test_excluded_tags(limits, blocked):
    assert generator.excluded_tags(limits) == blocked


def test_eligible_respects_time_and_accessibility():
    templates = [
        tpl("short", minutes=10),
        tpl("long", minutes=45),
        tpl("walk", minutes=10, requires=["walking"]),
    ]
    profile = make_profile(minutes_per_day=20, accessibility_limits=["uses a wheelchair"])
    assert [t.title for t in generator.eligible_templates(templates, profile)] == ["short"]


def test_pick_prefers_interests():
    candidates = [tpl("a", Domain.PHYSICAL), tpl("b", Domain.LEARNING)]
    profile = make_profile(interests=["learning"])
    assert pick(candidates, profile).domain == Domain.LEARNING


def test_pick_falls_back_to_other_domains_when_interests_are_exhausted():
    candidates = [tpl("a", Domain.PHYSICAL)]
    assert pick(candidates, make_profile(interests=["learning"])).title == "a"


def test_pick_rotates_away_from_avoided_and_recent_domains():
    candidates = [tpl("a", Domain.CREATIVE), tpl("b", Domain.SOCIAL), tpl("c", Domain.CARING)]
    history = History(domain_last_offered={Domain.SOCIAL: date(2026, 1, 1)})
    # creative is avoided (already in today's set); caring was never offered, social was.
    assert pick(candidates, history=history, avoid=[Domain.CREATIVE]).domain == Domain.CARING


def test_pick_matches_difficulty_to_level():
    candidates = [tpl(f"d{n}", difficulty=n) for n in range(1, 6)]
    assert pick(candidates, levels={Domain.CREATIVE: 4}).difficulty == 4


def test_pick_avoids_recent_templates_and_never_repeats_today():
    candidates = [tpl("same", difficulty=2), tpl("other", difficulty=3)]
    history = History(recent_titles={"same"})
    assert pick(candidates, history=history).title == "other"
    history = History(titles_today={"same", "other"})
    assert pick(candidates, history=history) is None
