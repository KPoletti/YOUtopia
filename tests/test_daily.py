import random
from datetime import date, timedelta

import pytest
from sqlmodel import select

from youtopia import daily
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
    assert len(session.exec(select(Task)).all()) == daily.MAX_TASKS_PER_DAY


def test_domains_rotate_across_days(session, profile):
    first = {t.domain for t in today(session, profile)}
    second = {t.domain for t in today(session, profile, DAY + timedelta(days=1))}
    assert first.isdisjoint(second)


def test_respects_accessibility_limits(session):
    data = profiles.ProfileInput(
        interests=[Domain.PHYSICAL],
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
    assert len(active) == daily.MAX_TASKS_PER_DAY
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
    task = daily.complete_task(session, DAY, 3, note="  lovely ")

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
