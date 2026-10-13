"""Adaptive difficulty: levels rise after consistent success and ease after declines or misses.

Only the per-domain level moves. Completions, streaks and milestones are never touched,
and easing is always worded kindly.
"""

from dataclasses import dataclass

from youtopia.models import MAX_LEVEL, MIN_LEVEL, Domain, SkillLevel

# Successes at or above the current level that raise it by one.
PROMOTE_AFTER_SUCCESSES = 3
# Declines (swaps) that ease the level by one.
EASE_AFTER_DECLINES = 3
# Tasks left unfinished on past days that ease the level by one.
EASE_AFTER_MISSES = 3


@dataclass(frozen=True)
class LevelChange:
    domain: Domain
    old: int
    new: int

    @property
    def raised(self) -> bool:
        return self.new > self.old

    def message(self) -> str:
        if self.raised:
            return (
                f"Level up: {self.domain} is now level {self.new}. "
                "Tasks there will stretch you a little more."
            )
        return (
            f"{self.domain.capitalize()} tasks are eased to level {self.new} for now. "
            "They'll grow again as you go."
        )


def record_success(skill: SkillLevel, difficulty: int) -> LevelChange | None:
    """Count a completion. Only tasks at or above the current level count towards promotion.

    A success also clears the decline and miss counts, so easing needs them in a row.
    """
    skill.recent_declines = 0
    skill.recent_misses = 0
    if difficulty >= skill.level:
        skill.recent_successes += 1
    if skill.recent_successes >= PROMOTE_AFTER_SUCCESSES:
        return _change(skill, +1)
    return None


def record_decline(skill: SkillLevel) -> LevelChange | None:
    skill.recent_declines += 1
    if skill.recent_declines >= EASE_AFTER_DECLINES:
        return _change(skill, -1)
    return None


def record_misses(skill: SkillLevel, misses: int) -> LevelChange | None:
    """Count tasks left unfinished. Eases by one level at most, however many were missed."""
    if misses <= 0:
        return None
    skill.recent_misses += misses
    if skill.recent_misses >= EASE_AFTER_MISSES:
        return _change(skill, -1)
    return None


def _change(skill: SkillLevel, step: int) -> LevelChange | None:
    """Move the level by `step` within bounds. Counters reset either way, even at a bound."""
    old = skill.level
    skill.level = max(MIN_LEVEL, min(MAX_LEVEL, old + step))
    skill.recent_successes = 0
    skill.recent_declines = 0
    skill.recent_misses = 0
    if skill.level == old:
        return None
    return LevelChange(domain=Domain(skill.domain), old=old, new=skill.level)
