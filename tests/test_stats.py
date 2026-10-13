import random
from datetime import date, timedelta

from youtopia import daily, stats
from youtopia import profile as profiles
from youtopia.models import Domain

DAY = date(2026, 10, 1)


def d(offset: int) -> date:
    return DAY + timedelta(days=offset)


def test_streak_forgives_short_gaps():
    days = [d(0), d(1), d(4), d(5)]  # two days off between d(1) and d(4)
    assert stats.current_streak(days, d(5)) == 4


def test_streak_ends_after_a_long_break_but_best_is_kept():
    days = [d(0), d(1), d(2)]
    gap = stats.STREAK_GRACE_DAYS + 2
    assert stats.current_streak(days, d(2 + gap)) == 0
    assert stats.current_streak(days, d(2 + gap - 1)) == 3
    assert [len(r) for r in stats.streak_runs([*days, d(2 + gap)])] == [3, 1]


def test_domain_milestone_survives_new_domains():
    reached, _ = stats.milestones(total=6, best_streak=0, domains_tried=len(Domain))
    assert "Tried 6 domains" in reached
    reached, _ = stats.milestones(total=5, best_streak=0, domains_tried=5)
    assert "Tried 6 domains" not in reached


def test_milestones():
    reached, upcoming = stats.milestones(total=5, best_streak=7, domains_tried=6)
    assert reached == [
        "First task done",
        "5 tasks done",
        "3-day streak",
        "7-day streak",
        "Tried 6 domains",
    ]
    assert upcoming == "10 tasks done (5 to go)"
    assert stats.milestones(0, 0, 0) == ([], "First task done (1 to go)")


def test_compute_stats(session):
    profile = profiles.save_profile(
        session, profiles.ProfileInput(interests=list(Domain), minutes_per_day=30)
    )
    for offset in range(3):
        daily.ensure_today(session, profile, d(offset), random.Random(offset))
        daily.complete_task(session, d(offset), 1, note=f"day {offset}")
    daily.complete_task(session, d(2), 2)

    result = stats.compute_stats(session, d(2))
    assert result.total_completed == 4
    assert result.active_days == 3
    assert result.current_streak == 3
    assert sum(ds.completed for ds in result.domains) == 4
    assert {ds.domain for ds in result.domains} == set(Domain)
    assert result.history[0].day == d(2)
    assert "First task done" in result.milestones
    assert "3-day streak" in result.milestones


def test_compute_stats_empty(session):
    result = stats.compute_stats(session, DAY)
    assert result.total_completed == 0
    assert result.current_streak == 0
    assert result.history == []
