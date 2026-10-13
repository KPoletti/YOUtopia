"""Daily cap on provider calls (ai.max_calls_per_day)."""

from datetime import date

from sqlmodel import Session

from youtopia.models import AIUsage


def calls_today(session: Session, day: date) -> int:
    usage = session.get(AIUsage, day)
    return usage.calls if usage else 0


def try_spend_call(session: Session, day: date, cap: int) -> bool:
    """Count one call if today's cap allows it. Returns False when the cap is reached."""
    usage = session.get(AIUsage, day) or AIUsage(day=day)
    if usage.calls >= cap:
        return False
    usage.calls += 1
    session.add(usage)
    session.flush()
    return True
