import random
from datetime import date, timedelta

import pytest
from sqlmodel import select

from youtopia import daily, difficulty, stats
from youtopia import profile as profiles
from youtopia.encouragement import GUILT_PHRASES
from youtopia.models import MAX_LEVEL, MIN_LEVEL, Domain, SkillLevel, Task, TaskStatus

DAY = date(2026, 10, 13)


def skill(level=2, **counts) -> SkillLevel:
    return SkillLevel(domain=Domain.PRODUCTION, level=level, **counts)


# --- rules ------------------------------------------------------------------


def test_promotes_after_enough_successes_at_or_above_level():
    s = skill(level=2)
    for _ in range(difficulty.PROMOTE_AFTER_SUCCESSES - 1):
        assert difficulty.record_success(s, difficulty=2) is None
    change = difficulty.record_success(s, difficulty=3)
    assert change == difficulty.LevelChange(Domain.PRODUCTION, 2, 3)
    assert change.raised
    assert (s.level, s.recent_successes) == (3, 0)


def test_easier_successes_dont_count_towards_promotion():
    s = skill(level=3)
    for _ in range(difficulty.PROMOTE_AFTER_SUCCESSES + 2):
        assert difficulty.record_success(s, difficulty=2) is None
    assert s.level == 3


def test_eases_after_declines():
    s = skill(level=3)
    for _ in range(difficulty.EASE_AFTER_DECLINES - 1):
        assert difficulty.record_decline(s) is None
    change = difficulty.record_decline(s)
    assert change == difficulty.LevelChange(Domain.PRODUCTION, 3, 2)
    assert not change.raised
    assert (s.level, s.recent_declines) == (2, 0)


def test_eases_after_misses_by_one_level_at_most():
    s = skill(level=4)
    assert difficulty.record_misses(s, 0) is None
    change = difficulty.record_misses(s, difficulty.EASE_AFTER_MISSES * 3)
    assert change.new == 3
    assert s.recent_misses == 0


def test_a_success_clears_declines_and_misses():
    s = skill(level=3, recent_declines=2, recent_misses=2)
    difficulty.record_success(s, difficulty=1)
    assert (s.recent_declines, s.recent_misses) == (0, 0)
    assert difficulty.record_decline(s) is None


def test_level_stays_within_bounds():
    top = skill(level=MAX_LEVEL, recent_successes=difficulty.PROMOTE_AFTER_SUCCESSES - 1)
    assert difficulty.record_success(top, difficulty=MAX_LEVEL) is None
    assert (top.level, top.recent_successes) == (MAX_LEVEL, 0)

    bottom = skill(level=MIN_LEVEL, recent_declines=difficulty.EASE_AFTER_DECLINES - 1)
    assert difficulty.record_decline(bottom) is None
    assert (bottom.level, bottom.recent_declines) == (MIN_LEVEL, 0)


@pytest.mark.parametrize("old, new", [(2, 3), (3, 2), (2, 1)])
def test_level_change_wording_is_kind(old, new):
    message = difficulty.LevelChange(Domain.OUTREACH, old, new).message().lower()
    assert not [p for p in GUILT_PHRASES if p in message]
    if new < old:
        assert "eased" in message


# --- daily hooks ------------------------------------------------------------


@pytest.fixture
def profile(session):
    data = profiles.ProfileInput(interests=list(Domain), minutes_per_day=60, preferred_challenge=2)
    return profiles.save_profile(session, data)


def get_skill(session, domain) -> SkillLevel:
    return session.exec(select(SkillLevel).where(SkillLevel.domain == domain)).one()


def offer(session, domain, day, status=TaskStatus.OFFERED, slot=1) -> Task:
    task = Task(
        title=f"{domain} {day}",
        instructions="Do it.",
        domain=domain,
        difficulty=2,
        duration_minutes=5,
        done_criteria="Done.",
        offered_on=day,
        slot=slot,
        status=status,
    )
    session.add(task)
    session.flush()
    return task


def test_swaps_count_as_declines_and_ease_the_level(session, profile):
    for i in range(difficulty.EASE_AFTER_DECLINES):
        day = DAY + timedelta(days=i)
        offer(session, Domain.CARETAKING, day)
        result = daily.swap_task(session, profile, day, 1, random.Random(0))
    assert result.level_change == difficulty.LevelChange(Domain.CARETAKING, 2, 1)
    assert get_skill(session, Domain.CARETAKING).level == 1


def test_completions_count_as_successes_and_raise_the_level(session, profile):
    for i in range(difficulty.PROMOTE_AFTER_SUCCESSES):
        day = DAY + timedelta(days=i)
        offer(session, Domain.LABOUR, day)
        result = daily.complete_task(session, day, 1)
    assert result.level_change == difficulty.LevelChange(Domain.LABOUR, 2, 3)


def test_unfinished_past_tasks_count_as_misses_once(session, profile):
    for i in range(difficulty.EASE_AFTER_MISSES):
        offer(session, Domain.OUTREACH, DAY - timedelta(days=10 + i))
    offer(session, Domain.OUTREACH, DAY - timedelta(days=1), status=TaskStatus.DONE, slot=2)
    offer(session, Domain.OUTREACH, DAY, slot=3)  # today's task isn't a miss yet

    changes = daily.evaluate_misses(session, profile, DAY)
    assert changes == [difficulty.LevelChange(Domain.OUTREACH, 2, 1)]
    # Running again (as `today` does) or next day with nothing new changes nothing.
    assert daily.evaluate_misses(session, profile, DAY) == []
    assert daily.ensure_today(session, profile, DAY, random.Random(0))
    assert get_skill(session, Domain.OUTREACH).recent_misses == 0
    assert daily.evaluate_misses(session, profile, DAY + timedelta(days=1)) == []


def test_misses_accumulate_across_gaps_without_counting_empty_days(session, profile):
    offer(session, Domain.TRAINING, DAY)
    # Ten days away: only the one unfinished task is a miss, not ten.
    daily.evaluate_misses(session, profile, DAY + timedelta(days=10))
    assert get_skill(session, Domain.TRAINING).recent_misses == 1

    offer(session, Domain.TRAINING, DAY + timedelta(days=10))
    offer(session, Domain.TRAINING, DAY + timedelta(days=20), slot=2)
    changes = daily.evaluate_misses(session, profile, DAY + timedelta(days=30))
    assert [c.new for c in changes] == [1]


def test_easing_leaves_stats_unchanged(session, profile):
    done = offer(session, Domain.PRODUCTION, DAY - timedelta(days=5))
    daily.complete_task(session, done.offered_on, 1, note="nice")
    for i in range(difficulty.EASE_AFTER_MISSES):
        offer(session, Domain.PRODUCTION, DAY - timedelta(days=4 - i))
    before = stats.compute_stats(session, DAY)

    assert daily.evaluate_misses(session, profile, DAY)
    after = stats.compute_stats(session, DAY)
    assert after.total_completed == before.total_completed
    assert after.milestones == before.milestones
    assert (after.current_streak, after.best_streak) == (before.current_streak, before.best_streak)
    assert after.history == before.history
