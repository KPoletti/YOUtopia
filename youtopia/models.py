"""SQLModel tables for YOUtopia."""

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from enum import StrEnum

from sqlmodel import JSON, Column, Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class Domain(StrEnum):
    PHYSICAL = "physical"
    CREATIVE = "creative"
    PRACTICAL = "practical"
    SOCIAL = "social"
    LEARNING = "learning"
    CARING = "caring"


class TaskStatus(StrEnum):
    OFFERED = "offered"
    DONE = "done"
    DECLINED = "declined"


MIN_LEVEL = 1
MAX_LEVEL = 5

TONE_MIN = 0
TONE_MAX = 5


@dataclass(frozen=True)
class ToneMix:
    """How much of each trait encouragement messages should carry, each TONE_MIN-TONE_MAX."""

    sincerity: int = 4
    humor: int = 1
    sarcasm: int = 0
    # Sarcasm and rudeness tease the task, never the person.
    rudeness: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


DEFAULT_TONE = ToneMix()
# Used when encouragement falls back after repeated misses or declines.
SINCERE_FALLBACK_TONE = ToneMix(sincerity=TONE_MAX, humor=0, sarcasm=0, rudeness=0)


class Profile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    interests: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    minutes_per_day: int = Field(ge=1)
    accessibility_limits: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    preferred_challenge: int = Field(ge=MIN_LEVEL, le=MAX_LEVEL)
    sincerity: int = Field(default=DEFAULT_TONE.sincerity, ge=TONE_MIN, le=TONE_MAX)
    humor: int = Field(default=DEFAULT_TONE.humor, ge=TONE_MIN, le=TONE_MAX)
    sarcasm: int = Field(default=DEFAULT_TONE.sarcasm, ge=TONE_MIN, le=TONE_MAX)
    rudeness: int = Field(default=DEFAULT_TONE.rudeness, ge=TONE_MIN, le=TONE_MAX)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    @property
    def tone(self) -> ToneMix:
        return ToneMix(self.sincerity, self.humor, self.sarcasm, self.rudeness)


class SkillLevel(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    domain: Domain = Field(unique=True)
    level: int = Field(default=MIN_LEVEL, ge=MIN_LEVEL, le=MAX_LEVEL)
    recent_successes: int = 0


class Task(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    instructions: str
    domain: Domain
    difficulty: int = Field(ge=MIN_LEVEL, le=MAX_LEVEL)
    duration_minutes: int = Field(ge=1)
    done_criteria: str
    offered_on: date = Field(index=True)
    # Position (1-3) in the day's set; a swap's replacement takes the declined task's slot.
    slot: int = Field(ge=1)
    status: TaskStatus = TaskStatus.OFFERED


class Completion(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="task.id", index=True)
    completed_at: datetime = Field(default_factory=_now)
    note: str | None = None
