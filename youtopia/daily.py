"""The daily loop: offering today's tasks, swapping and completing them."""

import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sqlmodel import Session, col, func, select

from youtopia import difficulty, generator, judge
from youtopia.difficulty import LevelChange
from youtopia.generator import AISource, History, TaskTemplate
from youtopia.models import (
    Completion,
    Domain,
    Profile,
    SkillLevel,
    Submission,
    Task,
    TaskSource,
    TaskStatus,
)
from youtopia.problems import Problem, starter_source

# Size of the set `today` opens with. `more_tasks` adds any number on top: no daily cap.
DAILY_SET_SIZE = 3


class DailyError(ValueError):
    """Raised for requests that can't be carried out. The message is shown to the user."""


@dataclass
class SwapResult:
    declined: Task
    replacement: Task | None
    level_change: LevelChange | None = None
    notice: str | None = None


@dataclass
class TodaySet:
    tasks: list[Task]
    notice: str | None = None  # e.g. why AI tasks were replaced by built-in ones


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
    ai: AISource | None = None,
) -> list[Task]:
    """Today's tasks, generating a fresh set if none have been offered yet."""
    return offer_today(session, profile, day, rng, templates, ai).tasks


def offer_today(
    session: Session,
    profile: Profile,
    day: date,
    rng: random.Random | None = None,
    templates: Sequence[TaskTemplate] | None = None,
    ai: AISource | None = None,
) -> TodaySet:
    """Like `ensure_today`, plus a notice when AI tasks fell back to templates.

    Unfinished tasks from past days are counted as misses first (see `evaluate_misses`).
    """
    evaluate_misses(session, profile, day)
    if existing := todays_tasks(session, day):
        return TodaySet(existing)
    generated = generator.generate(
        session,
        profile,
        day=day,
        n=DAILY_SET_SIZE,
        avoid_domains=set(),
        candidates=generator.eligible_templates(_templates(templates), profile),
        levels=_levels(session),
        history=_history(session, day),
        rng=rng or random.Random(),
        ai=ai,
    )
    tasks = [
        _task_from(template, day, slot, source)
        for slot, (template, source) in enumerate(generated.picks, start=1)
    ]
    session.add_all(tasks)
    session.flush()
    return TodaySet(tasks, generated.notice)


def more_tasks(
    session: Session,
    profile: Profile,
    day: date,
    count: int = 1,
    rng: random.Random | None = None,
    templates: Sequence[TaskTemplate] | None = None,
    ai: AISource | None = None,
) -> TodaySet:
    """Add `count` tasks to today's list, after the daily set. There is no daily cap; the
    only limit is what fits (the library, plus AI when it's on and within its call cap)."""
    if count < 1:
        raise DailyError("Ask for at least one more task.")
    rng = rng or random.Random()
    offer_today(session, profile, day, rng, templates, ai)
    active = todays_tasks(session, day)
    last_slot = session.exec(select(func.max(Task.slot)).where(Task.offered_on == day)).one()
    generated = generator.generate(
        session,
        profile,
        day=day,
        n=count,
        avoid_domains={t.domain for t in active},
        candidates=generator.eligible_templates(_templates(templates), profile),
        levels=_levels(session),
        history=_history(session, day),
        rng=rng,
        ai=ai,
    )
    tasks = [
        _task_from(template, day, (last_slot or 0) + i, source)
        for i, (template, source) in enumerate(generated.picks, start=1)
    ]
    session.add_all(tasks)
    session.flush()
    return TodaySet(tasks, generated.notice)


def swap_task(
    session: Session,
    profile: Profile,
    day: date,
    number: int,
    rng: random.Random | None = None,
    templates: Sequence[TaskTemplate] | None = None,
    ai: AISource | None = None,
) -> SwapResult:
    """Decline task `number` and offer a replacement in the same slot, if one fits."""
    task = _get_task(session, day, number)
    if task.status == TaskStatus.DONE:
        raise DailyError(f"Task {number} is already done, so there's nothing to swap.")
    task.status = TaskStatus.DECLINED
    task.declined_at = datetime.now(UTC)
    session.add(task)
    skill = _skill(session, task.domain, task.difficulty)
    level_change = difficulty.record_decline(skill)
    session.add(skill)

    others = [t for t in todays_tasks(session, day) if t.id != task.id]
    avoid = {t.domain for t in others} | {task.domain}
    generated = generator.generate(
        session,
        profile,
        day=day,
        n=1,
        avoid_domains=avoid,
        candidates=generator.eligible_templates(_templates(templates), profile),
        levels=_levels(session),
        history=_history(session, day),
        rng=rng or random.Random(),
        ai=ai,
    )
    replacement = None
    if generated.picks:
        template, source = generated.picks[0]
        replacement = _task_from(template, day, task.slot, source)
        session.add(replacement)
    session.flush()
    return SwapResult(
        declined=task,
        replacement=replacement,
        level_change=level_change,
        notice=generated.notice,
    )


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


@dataclass
class SubmitResult:
    task: Task
    verdict: judge.Verdict
    completion: CompletionResult | None = None  # set when this run completed the task


def submit_task(
    session: Session,
    day: date,
    number: int,
    solution: Path,
    run_tests=judge.run_tests,
) -> SubmitResult:
    """Run a solution against task `number`'s hidden tests and record the score.

    Passing every test completes the task (a success for difficulty). A failed attempt is
    recorded too, but never counts against you. Raises judge.JudgeError for unusable files.
    """
    task = _get_task(session, day, number)
    problem = task_problem(task, number)
    verdict = run_tests(solution, problem)
    session.add(Submission(task_id=task.id, passed=verdict.passed, total=verdict.total))
    completion = None
    if verdict.accepted and task.status != TaskStatus.DONE:
        completion = complete_task(session, day, number)
    session.flush()
    return SubmitResult(task, verdict, completion)


def starter_for(session: Session, day: date, number: int) -> tuple[Task, str]:
    """Task `number` and a solution skeleton for it."""
    task = _get_task(session, day, number)
    problem = task_problem(task, number)
    return task, starter_source(task.title, task.instructions, problem)


def task_problem(task: Task, number: int) -> Problem:
    if not task.problem:
        raise DailyError(
            f"Task {number} has no tests to run. Mark it done with `youtopia done {number}`."
        )
    return Problem.from_json(task.problem)


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


def _task_from(
    template: TaskTemplate, day: date, slot: int, source: TaskSource = TaskSource.TEMPLATE
) -> Task:
    return Task(
        title=template.title,
        instructions=template.instructions,
        domain=template.domain,
        difficulty=template.difficulty,
        duration_minutes=template.duration_minutes,
        done_criteria=template.done_criteria,
        offered_on=day,
        slot=slot,
        source=source,
        problem=template.problem.to_json() if template.problem else None,
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
