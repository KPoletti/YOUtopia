"""The daily loop: offering today's tasks, swapping and completing them."""

import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlmodel import Session, col, func, select

from youtopia import generator
from youtopia.generator import History, TaskTemplate
from youtopia.models import Completion, Domain, Profile, SkillLevel, Task, TaskStatus

MAX_TASKS_PER_DAY = 3


class DailyError(ValueError):
    """Raised for requests that can't be carried out. The message is shown to the user."""


@dataclass
class SwapResult:
    declined: Task
    replacement: Task | None


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
    """Return today's tasks, generating a fresh set if none have been offered yet."""
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
    return SwapResult(declined=task, replacement=replacement)


def complete_task(session: Session, day: date, number: int, note: str | None = None) -> Task:
    task = _get_task(session, day, number)
    if task.status == TaskStatus.DONE:
        raise DailyError(f"Task {number} is already marked done.")
    task.status = TaskStatus.DONE
    session.add(task)
    session.add(Completion(task_id=task.id, note=note or None))

    skill = session.exec(select(SkillLevel).where(SkillLevel.domain == task.domain)).first()
    if skill is None:
        skill = SkillLevel(domain=task.domain, level=task.difficulty)
    skill.recent_successes += 1
    session.add(skill)
    session.flush()
    return task


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
