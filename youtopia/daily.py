"""The daily loop: offering today's tasks, swapping and completing them."""

import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from sqlmodel import Session, col, func, select

from youtopia import difficulty, generator
from youtopia.difficulty import LevelChange
from youtopia.generator import History, TaskTemplate
from youtopia.models import Completion, Domain, Profile, SkillLevel, Task, TaskStatus

MAX_TASKS_PER_DAY = 3


class DailyError(ValueError):
    """Raised for requests that can't be carried out. The message is shown to the user."""


@dataclass
class SwapResult:
    declined: Task
    replacement: Task | None
    level_change: LevelChange | None = None


@dataclass
class CompletionResult:
    task: Task
    level_change: LevelChange | None = None


def todays_tasks(session: Session, day: date) -> list[Task]:
    """Today's active (not declined) tasks, in slot order."""
    return list(
        session.exec(
            select(Task)
            .where(Task.offered_on == day, Task.status != TaskStatus.DECLINED)
            .order_by(col(Task.slot))
        )
    )


def ensure_today(
    session: Session,
    profile: Profile,
    day: date,
    rng: random.Random | None = None,
    templates: Sequence[TaskTemplate] | None = None,
) -> list[Task]:
    """Return today's tasks, generating a fresh set if none have been offered yet.

    Unfinished tasks from past days are counted as misses first (see `evaluate_misses`).
    """
    evaluate_misses(session, profile, day)
    if existing := todays_tasks(session, day):
        return existing
    rng = rng or random.Random()
    candidates = generator.eligible_templates(_templates(templates), profile)
    history = _history(session, day)
    levels = _levels(session)

    tasks: list[Task] = []
    for slot in range(1, MAX_TASKS_PER_DAY + 1):
        avoid = {t.domain for t in tasks}
        template = generator.pick_template(candidates, profile, levels, history, avoid, rng)
        if template is None:
            break
        history.titles_today.add(template.title)
        tasks.append(_task_from(template, day, slot))
    session.add_all(tasks)
    session.flush()
    return tasks


def swap_task(
    session: Session,
    profile: Profile,
    day: date,
    number: int,
    rng: random.Random | None = None,
    templates: Sequence[TaskTemplate] | None = None,
) -> SwapResult:
    """Decline task `number` and offer a replacement in the same slot, if one fits."""
    task = _get_task(session, day, number)
    if task.status == TaskStatus.DONE:
        raise DailyError(f"Task {number} is already done, so there's nothing to swap.")
    task.status = TaskStatus.DECLINED
    session.add(task)
    skill = _skill(session, task.domain, task.difficulty)
    level_change = difficulty.record_decline(skill)
    session.add(skill)

    others = [t for t in todays_tasks(session, day) if t.id != task.id]
    avoid = {t.domain for t in others} | {task.domain}
    candidates = generator.eligible_templates(_templates(templates), profile)
    template = generator.pick_template(
        candidates, profile, _levels(session), _history(session, day), avoid, rng or random.Random()
    )
    replacement = _task_from(template, day, task.slot) if template else None
    if replacement:
        session.add(replacement)
    session.flush()
    return SwapResult(declined=task, replacement=replacement, level_change=level_change)


def complete_task(
    session: Session, day: date, number: int, note: str | None = None
) -> CompletionResult:
    task = _get_task(session, day, number)
    if task.status == TaskStatus.DONE:
        raise DailyError(f"Task {number} is already marked done.")
    task.status = TaskStatus.DONE
    session.add(task)
    session.add(Completion(task_id=task.id, note=note or None))

    skill = _skill(session, task.domain, task.difficulty)
    level_change = difficulty.record_success(skill, task.difficulty)
    session.add(skill)
    session.flush()
    return CompletionResult(task=task, level_change=level_change)


def evaluate_misses(session: Session, profile: Profile, day: date) -> list[LevelChange]:
    """Count tasks from past days that are still `offered` as misses, once each.

    Only days that had tasks can produce misses, so time away never piles up.
    Running it again on the same day changes nothing.
    """
    yesterday = day - timedelta(days=1)
    unfinished = session.exec(
        select(Task.domain, Task.offered_on).where(
            Task.status == TaskStatus.OFFERED, Task.offered_on < day
        )
    ).all()
    domains = {Domain(d) for d, _ in unfinished} | {
        Domain(s.domain) for s in session.exec(select(SkillLevel))
    }
    changes = []
    for domain in sorted(domains):
        skill = _skill(session, domain, profile.preferred_challenge)
        if skill.last_evaluated is not None and skill.last_evaluated >= yesterday:
            continue
        misses = sum(
            1
            for d, offered in unfinished
            if d == domain and (skill.last_evaluated is None or offered > skill.last_evaluated)
        )
        if change := difficulty.record_misses(skill, misses):
            changes.append(change)
        skill.last_evaluated = yesterday
        session.add(skill)
    session.flush()
    return changes


def _skill(session: Session, domain: Domain, default_level: int) -> SkillLevel:
    skill = session.exec(select(SkillLevel).where(SkillLevel.domain == domain)).first()
    return skill or SkillLevel(domain=domain, level=default_level)


def _get_task(session: Session, day: date, number: int) -> Task:
    tasks = todays_tasks(session, day)
    if not tasks:
        raise DailyError("No tasks yet today. Run `youtopia today` first.")
    for task in tasks:
        if task.slot == number:
            return task
    numbers = ", ".join(str(t.slot) for t in tasks)
    raise DailyError(f"There's no task {number} today. Pick one of: {numbers}.")


def _task_from(template: TaskTemplate, day: date, slot: int) -> Task:
    return Task(
        title=template.title,
        instructions=template.instructions,
        domain=template.domain,
        difficulty=template.difficulty,
        duration_minutes=template.duration_minutes,
        done_criteria=template.done_criteria,
        offered_on=day,
        slot=slot,
    )


def _templates(templates: Sequence[TaskTemplate] | None) -> Sequence[TaskTemplate]:
    return generator.load_templates() if templates is None else templates


def _levels(session: Session) -> dict[Domain, int]:
    return {s.domain: s.level for s in session.exec(select(SkillLevel))}


def _history(session: Session, day: date) -> History:
    recent = session.exec(
        select(Task.title, Task.offered_on).where(
            Task.offered_on >= generator.recent_cutoff(day), Task.offered_on <= day
        )
    ).all()
    last_offered = session.exec(
        select(Task.domain, func.max(Task.offered_on)).group_by(Task.domain)
    ).all()
    return History(
        titles_today={title for title, offered in recent if offered == day},
        recent_titles={title for title, offered in recent if offered < day},
        domain_last_offered={Domain(d): last for d, last in last_offered},
    )
