import pytest
from sqlmodel import select

from youtopia import profile as profiles
from youtopia.models import DEFAULT_TONE, Domain, SkillLevel, ToneMix


def make_input(**overrides) -> profiles.ProfileInput:
    values = dict(
        interests=[Domain.CREATIVE, Domain.LEARNING],
        minutes_per_day=20,
        accessibility_limits=["no kneeling"],
        preferred_challenge=3,
        tone=DEFAULT_TONE,
    )
    values.update(overrides)
    return profiles.ProfileInput(**values)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("creative, Learning", [Domain.CREATIVE, Domain.LEARNING]),
        ("social,social", [Domain.SOCIAL]),
        ("all", list(Domain)),
        (" ALL ", list(Domain)),
    ],
)
def test_parse_interests(raw, expected):
    assert profiles.parse_interests(raw) == expected


@pytest.mark.parametrize("raw", ["", " , ", "cooking", "creative, juggling"])
def test_parse_interests_rejects_bad_input(raw):
    with pytest.raises(profiles.ProfileError):
        profiles.parse_interests(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("none", []),
        ("", []),
        ("N/A", []),
        ("low vision,  no stairs ", ["low vision", "no stairs"]),
    ],
)
def test_parse_accessibility(raw, expected):
    assert profiles.parse_accessibility(raw) == expected


@pytest.mark.parametrize(
    "overrides",
    [
        {"interests": []},
        {"minutes_per_day": 0},
        {"minutes_per_day": 24 * 60 + 1},
        {"preferred_challenge": 0},
        {"preferred_challenge": 6},
        {"tone": ToneMix(sincerity=6)},
        {"tone": ToneMix(rudeness=-1)},
    ],
)
def test_save_profile_validates(session, overrides):
    with pytest.raises(profiles.ProfileError):
        profiles.save_profile(session, make_input(**overrides))


def test_save_profile_creates_profile_and_skill_levels(session):
    saved = profiles.save_profile(session, make_input())

    assert saved.interests == ["creative", "learning"]
    assert saved.minutes_per_day == 20
    assert saved.accessibility_limits == ["no kneeling"]
    assert saved.tone == DEFAULT_TONE

    levels = session.exec(select(SkillLevel)).all()
    assert {s.domain for s in levels} == set(Domain)
    assert all(s.level == 3 for s in levels)


def test_tone_defaults_to_mostly_sincere():
    data = profiles.ProfileInput(interests=[Domain.CARING], minutes_per_day=10)
    assert data.tone == ToneMix(sincerity=4, humor=1, sarcasm=0, rudeness=0)


def test_resave_updates_single_profile_and_keeps_progress(session):
    profiles.save_profile(session, make_input())
    creative = session.exec(select(SkillLevel).where(SkillLevel.domain == Domain.CREATIVE)).one()
    creative.level = 5
    creative.recent_successes = 4
    session.add(creative)
    session.commit()

    profiles.save_profile(session, make_input(preferred_challenge=1, tone=ToneMix(1, 2, 3, 4)))
    session.commit()

    assert profiles.get_profile(session).tone == ToneMix(1, 2, 3, 4)
    assert len(session.exec(select(profiles.Profile)).all()) == 1
    creative = session.exec(select(SkillLevel).where(SkillLevel.domain == Domain.CREATIVE)).one()
    assert (creative.level, creative.recent_successes) == (5, 4)
