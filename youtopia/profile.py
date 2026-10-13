"""Profile parsing, validation and persistence."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlmodel import Session, select

from youtopia.models import (
    DEFAULT_TONE,
    MAX_LEVEL,
    MIN_LEVEL,
    TONE_MAX,
    TONE_MIN,
    Domain,
    Profile,
    SkillLevel,
    ToneMix,
)

MAX_MINUTES_PER_DAY = 24 * 60
NONE_WORDS = {"", "none", "no", "n/a", "-"}
ALL_WORDS = {"all", "any", "everything"}


class ProfileError(ValueError):
    """Raised when profile input is invalid. The message is shown to the user."""


@dataclass
class ProfileInput:
    interests: list[Domain]
    minutes_per_day: int
    accessibility_limits: list[str] = field(default_factory=list)
    preferred_challenge: int = 2
    tone: ToneMix = DEFAULT_TONE


def split_list(raw: str) -> list[str]:
    """Split comma-separated input, dropping blanks and duplicates (order kept)."""
    items = [part.strip() for part in raw.split(",")]
    return list(dict.fromkeys(item for item in items if item))


def parse_interests(raw: str) -> list[Domain]:
    if raw.strip().lower() in ALL_WORDS:
        return list(Domain)
    names = [name.lower() for name in split_list(raw)]
    if not names:
        raise ProfileError("Pick at least one interest.")
    valid = {d.value for d in Domain}
    unknown = [name for name in names if name not in valid]
    if unknown:
        raise ProfileError(
            f"Unknown interest(s): {', '.join(unknown)}. "
            f"Choose from: {', '.join(valid_domain_names())}, or 'all'."
        )
    return [Domain(name) for name in names]


def parse_accessibility(raw: str) -> list[str]:
    if raw.strip().lower() in NONE_WORDS:
        return []
    return split_list(raw)


def valid_domain_names() -> list[str]:
    return [d.value for d in Domain]


def validate(data: ProfileInput) -> None:
    if not data.interests:
        raise ProfileError("Pick at least one interest.")
    if not 1 <= data.minutes_per_day <= MAX_MINUTES_PER_DAY:
        raise ProfileError(f"Minutes per day must be between 1 and {MAX_MINUTES_PER_DAY}.")
    if not MIN_LEVEL <= data.preferred_challenge <= MAX_LEVEL:
        raise ProfileError(f"Preferred challenge must be between {MIN_LEVEL} and {MAX_LEVEL}.")
    for trait, value in data.tone.as_dict().items():
        if not TONE_MIN <= value <= TONE_MAX:
            raise ProfileError(f"{trait.capitalize()} must be between {TONE_MIN} and {TONE_MAX}.")


def input_from(profile: Profile) -> ProfileInput:
    """The editable fields of a saved profile, ready to change and save again."""
    return ProfileInput(
        interests=[Domain(i) for i in profile.interests],
        minutes_per_day=profile.minutes_per_day,
        accessibility_limits=list(profile.accessibility_limits),
        preferred_challenge=profile.preferred_challenge,
        tone=profile.tone,
    )


def get_profile(session: Session) -> Profile | None:
    return session.exec(select(Profile)).first()


def save_profile(session: Session, data: ProfileInput) -> Profile:
    """Create or update the single profile and make sure every domain has a skill level.

    Existing skill levels are left untouched so re-running onboarding never removes progress.
    """
    validate(data)
    profile = get_profile(session) or Profile(minutes_per_day=1, preferred_challenge=MIN_LEVEL)
    profile.interests = [d.value for d in data.interests]
    profile.minutes_per_day = data.minutes_per_day
    profile.accessibility_limits = list(data.accessibility_limits)
    profile.preferred_challenge = data.preferred_challenge
    for trait, value in data.tone.as_dict().items():
        setattr(profile, trait, value)
    profile.updated_at = datetime.now(UTC)
    session.add(profile)

    existing = {s.domain for s in session.exec(select(SkillLevel))}
    for domain in Domain:
        if domain not in existing:
            session.add(SkillLevel(domain=domain, level=data.preferred_challenge))

    session.flush()
    session.refresh(profile)
    return profile
