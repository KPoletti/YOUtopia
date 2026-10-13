import random
from datetime import date, timedelta

import pytest
from sqlmodel import select

from youtopia import daily, generator
from youtopia import profile as profiles
from youtopia.models import Completion, Domain, SkillLevel, Task, TaskStatus

DAY = date(2026, 10, 13)


@pytest.fixture
def profile(session):
    data = profiles.ProfileInput(interests=list(Domain), minutes_per_day=30, preferred_challenge=2)
    return profiles.save_profile(session, data)


def today(session, profile, day=DAY, seed=0):
    return daily.ensure_today(session, profile, day, random.Random(seed))


def test_ensure_today_offers_three_tasks_in_distinct_domains(session, profile):
    tasks = today(session, profile)
    assert [t.slot for t in tasks] == [1, 2, 3]
    assert len({t.domain for t in tasks}) == 3
    assert all(t.duration_minutes <= 30 for t in tasks)
    assert all(t.status == TaskStatus.OFFERED for t in tasks)


def test_ensure_today_is_stable_within_a_day(session, profile):
    first = today(session, profile, seed=1)
    second = today(session, profile, seed=2)
    assert [t.id for t in first] == [t.id for t in second]
    assert len(session.exec(select(Task)).all()) == daily.DAILY_SET_SIZE


def test_domains_rotate_across_days(session, profile):
    first = {t.domain for t in today(session, profile)}
    second = {t.domain for t in today(session, profile, DAY + timedelta(days=1))}
    assert first.isdisjoint(second)


def test_respects_accessibility_limits(session):
    data = profiles.ProfileInput(
        interests=[Domain.LABOUR],
        minutes_per_day=60,
        accessibility_limits=["wheelchair user"],
    )
    profile = profiles.save_profile(session, data)
    tasks = today(session, profile)
    titles = {t.title for t in tasks}
    assert "Five-minute stroll" not in titles
    assert "Walk around the block" not in titles


def test_offers_fewer_when_nothing_else_fits(session):
    data = profiles.ProfileInput(interests=list(Domain), minutes_per_day=1)
    profile = profiles.save_profile(session, data)
    assert today(session, profile) == []


def test_swap_declines_and_replaces_in_same_slot(session, profile):
    tasks = today(session, profile)
    result = daily.swap_task(session, profile, DAY, 2, random.Random(0))

    assert result.declined.status == TaskStatus.DECLINED
    assert result.replacement.slot == 2
    assert result.replacement.title not in {t.title for t in tasks}
    active = daily.todays_tasks(session, DAY)
    assert len(active) == daily.DAILY_SET_SIZE
    assert len({t.domain for t in active}) == 3


def test_swap_never_repeats_a_template_within_the_day(session, profile):
    today(session, profile)
    for _ in range(15):
        daily.swap_task(session, profile, DAY, 1, random.Random(0))
    titles = [t.title for t in session.exec(select(Task))]
    assert len(titles) == len(set(titles))


def test_swap_rejects_done_and_unknown_tasks(session, profile):
    today(session, profile)
    daily.complete_task(session, DAY, 1)
    with pytest.raises(daily.DailyError, match="already done"):
        daily.swap_task(session, profile, DAY, 1)
    with pytest.raises(daily.DailyError, match="no task 7"):
        daily.swap_task(session, profile, DAY, 7)


def test_complete_records_completion_and_success(session, profile):
    tasks = today(session, profile)
    task = daily.complete_task(session, DAY, 3, note="  lovely ").task

    assert task.status == TaskStatus.DONE
    completion = session.exec(select(Completion)).one()
    assert completion.task_id == tasks[2].id
    assert completion.note == "  lovely "
    skill = session.exec(select(SkillLevel).where(SkillLevel.domain == task.domain)).one()
    assert skill.recent_successes == 1


def test_complete_twice_is_rejected(session, profile):
    today(session, profile)
    daily.complete_task(session, DAY, 1)
    with pytest.raises(daily.DailyError, match="already marked done"):
        daily.complete_task(session, DAY, 1)


def test_actions_before_today_ask_to_run_today(session, profile):
    with pytest.raises(daily.DailyError, match="youtopia today"):
        daily.complete_task(session, DAY, 1)


def test_more_adds_tasks_past_the_daily_set(session, profile):
    today(session, profile)
    added = daily.more_tasks(session, profile, DAY, 10, random.Random(0)).tasks
    assert [t.slot for t in added] == list(range(4, 14))
    active = daily.todays_tasks(session, DAY)
    assert len(active) == 13  # no daily cap
    assert len({t.title for t in active}) == 13  # never the same task twice in a day
    assert len({t.domain for t in added[:4]}) == 4  # still rotates areas


def test_more_starts_the_day_if_needed_and_keeps_slots_unique(session, profile):
    added = daily.more_tasks(session, profile, DAY, 1, random.Random(0)).tasks
    assert added[0].slot == daily.DAILY_SET_SIZE + 1
    daily.swap_task(session, profile, DAY, 4, random.Random(0))
    more = daily.more_tasks(session, profile, DAY, 1, random.Random(0)).tasks
    assert more[0].slot == 5
    assert daily.complete_task(session, DAY, 5).task.id == more[0].id


def test_more_stops_when_the_library_runs_out(session, profile):
    available = len(generator.eligible_templates(generator.load_templates(), profile))
    added = daily.more_tasks(session, profile, DAY, available + 50, random.Random(0)).tasks
    assert len(daily.todays_tasks(session, DAY)) == available
    assert len(added) == available - daily.DAILY_SET_SIZE


def test_more_needs_a_positive_count(session, profile):
    with pytest.raises(daily.DailyError):
        daily.more_tasks(session, profile, DAY, 0)
