"""Progress summaries: skill levels, history, streaks and milestones."""

from collections import Counter
from dataclasses import dataclass
from datetime import date

from sqlmodel import Session, col, select

from youtopia.models import Completion, Domain, SkillLevel, Submission, Task

# A streak survives this many missed days in a row; missing days never resets totals.
STREAK_GRACE_DAYS = 2
COMPLETION_MILESTONES = (1, 5, 10, 25, 50, 100, 250, 500)
STREAK_MILESTONES = (3, 7, 30, 100)
# Fixed at the original six areas, so adding an area never takes the milestone away.
DOMAINS_MILESTONE = 6
HISTORY_LIMIT = 10


@dataclass
class DomainStats:
    domain: Domain
    level: int | None
    recent_successes: int
    completed: int


@dataclass
class HistoryEntry:
    day: date
    title: str
    domain: Domain
    note: str | None
    score: str | None = None  # best "passed/total" from `youtopia submit`, if any


@dataclass
class Stats:
    domains: list[DomainStats]
    total_completed: int
    active_days: int
    current_streak: int
    best_streak: int
    history: list[HistoryEntry]
    milestones: list[str]
    next_milestone: str | None
    solved_by_tests: int = 0  # completions where every hidden test passed


def streak_runs(active_days: list[date]) -> list[list[date]]:
    """Group sorted active days into runs, allowing up to STREAK_GRACE_DAYS gaps."""
    runs: list[list[date]] = []
    for day in sorted(set(active_days)):
        if runs and (day - runs[-1][-1]).days <= STREAK_GRACE_DAYS + 1:
            runs[-1].append(day)
        else:
            runs.append([day])
    return runs


def current_streak(active_days: list[date], today: date) -> int:
    runs = streak_runs(active_days)
    if not runs or (today - runs[-1][-1]).days > STREAK_GRACE_DAYS + 1:
        return 0
    return len(runs[-1])


def milestones(total: int, best_streak: int, domains_tried: int) -> tuple[list[str], str | None]:
    reached = [_completion_label(n) for n in COMPLETION_MILESTONES if total >= n]
    reached += [f"{n}-day streak" for n in STREAK_MILESTONES if best_streak >= n]
    if domains_tried >= DOMAINS_MILESTONE:
        reached.append(f"Tried {DOMAINS_MILESTONE} domains")
    upcoming = next((n for n in COMPLETION_MILESTONES if total < n), None)
    next_label = f"{_completion_label(upcoming)} ({upcoming - total} to go)" if upcoming else None
    return reached, next_label


def _completion_label(n: int) -> str:
    return "First task done" if n == 1 else f"{n} tasks done"


def compute_stats(session: Session, today: date) -> Stats:
    rows = session.exec(
        select(Task, Completion)
        .join(Completion, col(Completion.task_id) == col(Task.id))
        .order_by(col(Completion.completed_at).desc())
    ).all()
    per_domain = Counter(task.domain for task, _ in rows)
    skills = {s.domain: s for s in session.exec(select(SkillLevel))}
    active = [task.offered_on for task, _ in rows]
    best = max((len(run) for run in streak_runs(active)), default=0)
    reached, upcoming = milestones(len(rows), best, len(per_domain))
    best_scores: dict[int, tuple[int, int]] = {}
    for sub in session.exec(select(Submission)):
        if sub.task_id not in best_scores or sub.passed > best_scores[sub.task_id][0]:
            best_scores[sub.task_id] = (sub.passed, sub.total)
    solved = sum(1 for p, t in best_scores.values() if t and p == t)

    return Stats(
        domains=[
            DomainStats(
                domain=d,
                level=skills[d].level if d in skills else None,
                recent_successes=skills[d].recent_successes if d in skills else 0,
                completed=per_domain[d],
            )
            for d in Domain
        ],
        total_completed=len(rows),
        active_days=len(set(active)),
        current_streak=current_streak(active, today),
        best_streak=best,
        history=[
            HistoryEntry(
                day=task.offered_on,
                title=task.title,
                domain=task.domain,
                note=c.note,
                score="{}/{}".format(*best_scores[task.id]) if task.id in best_scores else None,
            )
            for task, c in rows[:HISTORY_LIMIT]
        ],
        milestones=reached,
        next_milestone=upcoming,
        solved_by_tests=solved,
    )
