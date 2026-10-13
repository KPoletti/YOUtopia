"""Task generation. Templates only for now; AI generation arrives in a later milestone."""

import random
import re
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import cache
from importlib import resources

import yaml

from youtopia.models import MAX_LEVEL, MIN_LEVEL, Domain, Profile

# Don't repeat a template offered within this many days, if anything else fits.
RECENT_TEMPLATE_DAYS = 7

# Requirement tag -> patterns that, found in a user's accessibility limits, rule it out.
LIMIT_PATTERNS: dict[str, tuple[str, ...]] = {
    "standing": (r"\bstand", r"wheelchair", r"\bseated\b", r"sit(ting)? only"),
    "walking": (r"\bwalk", r"wheelchair", r"mobility", r"\bcrutch", r"\bcane\b"),
    "kneeling": (r"\bkneel", r"\bknees?\b"),
    "lifting": (r"\blift", r"\bback\b", r"\bheavy\b"),
    "exertion": (
        r"\bheart\b", r"\bbreath", r"\basthma", r"low energy", r"fatigue",
        r"chronic pain", r"no exercise", r"\bexert",
    ),
    "hands": (r"\bhands?\b", r"fine motor", r"\bgrip\b", r"\bdexterity\b"),
    "vision": (r"\bvision\b", r"\bblind", r"\bsight", r"visual"),
    "hearing": (r"\bhearing\b", r"\bdeaf", r"hard of hearing"),
    "speaking": (r"\bspeak", r"\bspeech\b", r"non-?verbal", r"\bmute\b", r"\bvoice\b"),
    "going_out": (
        r"housebound", r"home ?bound", r"bedbound", r"agoraphob",
        r"can'?t (go|get) out", r"\bindoors?\b", r"stay (at )?home", r"no going out",
    ),
}  # fmt: skip
KNOWN_TAGS = frozenset(LIMIT_PATTERNS)


class TemplateError(ValueError):
    """Raised when the template library is malformed."""


@dataclass(frozen=True)
class TaskTemplate:
    title: str
    instructions: str
    domain: Domain
    difficulty: int
    duration_minutes: int
    done_criteria: str
    requires: frozenset[str] = field(default_factory=frozenset)


@dataclass
class History:
    """What has already been offered, so new picks can avoid repeats."""

    titles_today: set[str] = field(default_factory=set)
    recent_titles: set[str] = field(default_factory=set)
    domain_last_offered: dict[Domain, date] = field(default_factory=dict)


def _parse_template(raw: dict) -> TaskTemplate:
    try:
        template = TaskTemplate(
            title=raw["title"],
            instructions=raw["instructions"],
            domain=Domain(raw["domain"]),
            difficulty=int(raw["difficulty"]),
            duration_minutes=int(raw["duration_minutes"]),
            done_criteria=raw["done_criteria"],
            requires=frozenset(raw.get("requires", [])),
        )
    except (KeyError, ValueError, TypeError) as err:
        raise TemplateError(f"Bad template {raw.get('title', raw)!r}: {err}") from err
    if not MIN_LEVEL <= template.difficulty <= MAX_LEVEL:
        raise TemplateError(f"{template.title!r}: difficulty out of range")
    if template.duration_minutes < 1:
        raise TemplateError(f"{template.title!r}: duration must be positive")
    if unknown := template.requires - KNOWN_TAGS:
        raise TemplateError(f"{template.title!r}: unknown requirement tags {sorted(unknown)}")
    return template


def parse_templates(text: str) -> list[TaskTemplate]:
    templates = [_parse_template(raw) for raw in yaml.safe_load(text) or []]
    titles = [t.title for t in templates]
    if len(titles) != len(set(titles)):
        raise TemplateError("Template titles must be unique.")
    return templates


@cache
def load_templates() -> tuple[TaskTemplate, ...]:
    text = resources.files("youtopia").joinpath("templates.yaml").read_text(encoding="utf-8")
    return tuple(parse_templates(text))


def excluded_tags(accessibility_limits: Iterable[str]) -> set[str]:
    text = " ".join(accessibility_limits).lower()
    return {
        tag
        for tag, patterns in LIMIT_PATTERNS.items()
        if any(re.search(pattern, text) for pattern in patterns)
    }


def eligible_templates(templates: Iterable[TaskTemplate], profile: Profile) -> list[TaskTemplate]:
    """Templates that fit the user's daily time and accessibility limits. Never relaxed."""
    blocked = excluded_tags(profile.accessibility_limits)
    return [
        t
        for t in templates
        if t.duration_minutes <= profile.minutes_per_day and not (t.requires & blocked)
    ]


def pick_template(
    candidates: Collection[TaskTemplate],
    profile: Profile,
    levels: Mapping[Domain, int],
    history: History,
    avoid_domains: Collection[Domain],
    rng: random.Random,
) -> TaskTemplate | None:
    """Choose one template, rotating domains and matching difficulty to skill level.

    Prefers, in order: the user's interests over other domains, domains not in
    `avoid_domains` (the rest of today's set), domains least recently offered,
    templates not offered recently, and difficulty closest to the domain's level.
    Never offers the same template twice in one day.
    """
    pool = [t for t in candidates if t.title not in history.titles_today]
    if not pool:
        return None
    interests = {Domain(i) for i in profile.interests}
    available = {t.domain for t in pool}

    def domain_rank(domain: Domain) -> tuple:
        return (
            domain not in interests,
            domain in avoid_domains,
            history.domain_last_offered.get(domain, date.min),
            rng.random(),
        )

    domain = min(available, key=domain_rank)
    level = levels.get(domain, profile.preferred_challenge)

    def template_rank(template: TaskTemplate) -> tuple:
        return (
            template.title in history.recent_titles,
            abs(template.difficulty - level),
            rng.random(),
        )

    return min((t for t in pool if t.domain == domain), key=template_rank)


def recent_cutoff(day: date) -> date:
    return day - timedelta(days=RECENT_TEMPLATE_DAYS)
