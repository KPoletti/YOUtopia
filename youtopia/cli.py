"""Typer app: parses input and renders output. Business logic lives in other modules."""

from collections.abc import Callable
from datetime import date
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlmodel import Session

from youtopia import daily, stats
from youtopia import profile as profiles
from youtopia.db import session_scope
from youtopia.models import (
    DEFAULT_TONE,
    MAX_LEVEL,
    MIN_LEVEL,
    TONE_MAX,
    TONE_MIN,
    Profile,
    Task,
    TaskStatus,
    ToneMix,
)

TONE_PROMPTS = {
    "sincerity": "Sincerity (warm, genuine praise)",
    "humor": "Humor (playful, light jokes)",
    "sarcasm": "Sarcasm (dry teasing of the task)",
    "rudeness": "Rudeness (blunt jabs at the task, never at you)",
}

app = typer.Typer(help="Small, achievable daily tasks matched to you.", no_args_is_help=True)
console = Console()


@app.callback()
def main() -> None:
    """Small, achievable daily tasks matched to you."""


def _ask[T](question: str, parse: Callable[[str], T], default: str) -> T:
    """Prompt until the answer parses."""
    while True:
        raw = typer.prompt(question, default=default, show_default=bool(default))
        try:
            return parse(raw)
        except profiles.ProfileError as err:
            console.print(f"[yellow]{err}[/yellow]")


def _from_flag[T](raw: str, parse: Callable[[str], T]) -> T:
    try:
        return parse(raw)
    except profiles.ProfileError as err:
        console.print(f"[red]{err}[/red]")
        raise typer.Exit(code=2) from None


def _parse_int_in(low: int, high: int, label: str) -> Callable[[str], int]:
    def parse(raw: str) -> int:
        try:
            value = int(raw.strip())
        except ValueError:
            raise profiles.ProfileError(f"{label} must be a whole number.") from None
        if not low <= value <= high:
            raise profiles.ProfileError(f"{label} must be between {low} and {high}.")
        return value

    return parse


def _render_profile(profile: Profile) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("Interests", ", ".join(profile.interests))
    table.add_row("Minutes per day", str(profile.minutes_per_day))
    table.add_row("Accessibility limits", ", ".join(profile.accessibility_limits) or "none")
    table.add_row("Preferred challenge", f"{profile.preferred_challenge} / {MAX_LEVEL}")
    for trait, value in profile.tone.as_dict().items():
        bar = "■" * value + "□" * (TONE_MAX - value)
        table.add_row(trait.capitalize(), f"{bar} {value}")
    console.print(Panel(table, title="Your profile", expand=False))


def _choose_tone(flags: dict[str, int | None], scripted: bool) -> ToneMix:
    """Use any tone flags given (defaults for the rest); otherwise ask, unless scripted."""
    defaults = DEFAULT_TONE.as_dict()
    if scripted or any(v is not None for v in flags.values()):
        parsers = {t: _parse_int_in(TONE_MIN, TONE_MAX, t.capitalize()) for t in flags}
        return ToneMix(
            **{
                t: defaults[t] if v is None else _from_flag(str(v), parsers[t])
                for t, v in flags.items()
            }
        )

    summary = ", ".join(f"{t} {v}" for t, v in defaults.items())
    if not typer.confirm(f"Customise encouragement tone? (default: {summary})", default=False):
        return DEFAULT_TONE
    console.print(f"Set each from {TONE_MIN} (none) to {TONE_MAX} (lots).")
    return ToneMix(
        **{
            t: _ask(question, _parse_int_in(TONE_MIN, TONE_MAX, t.capitalize()), str(defaults[t]))
            for t, question in TONE_PROMPTS.items()
        }
    )


@app.command()
def init(
    interests: Annotated[
        str | None, typer.Option(help="Comma-separated domains, or 'all'.")
    ] = None,
    minutes: Annotated[int | None, typer.Option(help="Minutes you can spare per day.")] = None,
    accessibility: Annotated[
        str | None, typer.Option(help="Comma-separated limits, or 'none'.")
    ] = None,
    challenge: Annotated[
        int | None, typer.Option(help=f"Preferred challenge, {MIN_LEVEL}-{MAX_LEVEL}.")
    ] = None,
    sincerity: Annotated[
        int | None, typer.Option(help=f"Tone slider, {TONE_MIN}-{TONE_MAX}.")
    ] = None,
    humor: Annotated[int | None, typer.Option(help=f"Tone slider, {TONE_MIN}-{TONE_MAX}.")] = None,
    sarcasm: Annotated[
        int | None, typer.Option(help=f"Tone slider, {TONE_MIN}-{TONE_MAX}.")
    ] = None,
    rudeness: Annotated[
        int | None, typer.Option(help=f"Tone slider, {TONE_MIN}-{TONE_MAX}.")
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Overwrite without asking.")] = False,
) -> None:
    """Set up your profile. Takes about a minute."""
    with session_scope() as session:
        if profiles.get_profile(session) and not yes:
            typer.confirm(
                "You already have a profile. Update it? (Your progress is kept.)", abort=True
            )

    console.print(
        Panel(
            "Welcome to [bold]YOUtopia[/bold]. A few quick questions and you're set.\n"
            "Every answer can be changed later.",
            expand=False,
        )
    )

    # Every other answer came from flags, so don't stop to ask about tone.
    scripted = None not in (interests, minutes, accessibility, challenge)
    minutes_parser = _parse_int_in(1, profiles.MAX_MINUTES_PER_DAY, "Minutes per day")
    challenge_parser = _parse_int_in(MIN_LEVEL, MAX_LEVEL, "Preferred challenge")

    if interests is None:
        console.print(f"Interest areas: {', '.join(profiles.valid_domain_names())}")
        chosen = _ask(
            "Which interest you? (comma-separated, or 'all')", profiles.parse_interests, "all"
        )
    else:
        chosen = _from_flag(interests, profiles.parse_interests)

    if minutes is None:
        minutes = _ask("How many minutes a day can you spare?", minutes_parser, "20")
    else:
        minutes = _from_flag(str(minutes), minutes_parser)

    if accessibility is None:
        limits = _ask(
            "Anything we should work around? (e.g. 'no kneeling, low vision', or 'none')",
            profiles.parse_accessibility,
            "none",
        )
    else:
        limits = profiles.parse_accessibility(accessibility)

    if challenge is None:
        challenge = _ask(
            f"How challenging should tasks be? ({MIN_LEVEL}=gentle, {MAX_LEVEL}=stretch)",
            challenge_parser,
            "2",
        )
    else:
        challenge = _from_flag(str(challenge), challenge_parser)

    chosen_tone = _choose_tone(
        {"sincerity": sincerity, "humor": humor, "sarcasm": sarcasm, "rudeness": rudeness},
        scripted,
    )

    data = profiles.ProfileInput(
        interests=chosen,
        minutes_per_day=minutes,
        accessibility_limits=limits,
        preferred_challenge=challenge,
        tone=chosen_tone,
    )
    with session_scope() as session:
        saved = profiles.save_profile(session, data)
        _render_profile(saved)

    console.print("[green]All set.[/green] Your profile is saved.")


def _today() -> date:
    return date.today()


def _require_profile(session: Session) -> Profile:
    profile = profiles.get_profile(session)
    if profile is None:
        console.print("You don't have a profile yet. Run [bold]youtopia init[/bold] first.")
        raise typer.Exit(code=1)
    return profile


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _level_dots(level: int) -> str:
    return "●" * level + "○" * (MAX_LEVEL - level)


def _render_task(task: Task) -> None:
    done = task.status == TaskStatus.DONE
    meta = f"{task.domain} · {_level_dots(task.difficulty)} · {task.duration_minutes} min"
    body = f"{task.instructions}\n\n[dim]Done when:[/dim] {task.done_criteria}"
    title = f"{task.slot}. {task.title}" + (" [green]✓ done[/green]" if done else "")
    console.print(
        Panel(
            body,
            title=title,
            subtitle=meta,
            title_align="left",
            subtitle_align="right",
            border_style="green" if done else "cyan",
        )
    )


@app.command()
def today() -> None:
    """Show today's tasks, picking a fresh set if needed."""
    with session_scope() as session:
        profile = _require_profile(session)
        tasks = daily.ensure_today(session, profile, _today())
        if not tasks:
            console.print(
                "Nothing in the library fits your time and accessibility limits right now. "
                "Try [bold]youtopia init[/bold] to adjust them."
            )
            return
        for task in tasks:
            _render_task(task)
    console.print(
        "[dim]Finished one? [bold]youtopia done <n>[/bold]. "
        "Not feeling it? [bold]youtopia swap <n>[/bold].[/dim]"
    )


@app.command()
def swap(number: Annotated[int, typer.Argument(help="Task number from `youtopia today`.")]) -> None:
    """Swap a task for a different one. No questions asked."""
    with session_scope() as session:
        profile = _require_profile(session)
        try:
            result = daily.swap_task(session, profile, _today(), number)
        except daily.DailyError as err:
            console.print(f"[yellow]{err}[/yellow]")
            raise typer.Exit(code=1) from None
        if result.replacement is None:
            console.print(
                f'Swapped out "{result.declined.title}". '
                "That's every option that fits today, so enjoy the space."
            )
            return
        console.print(f'Swapped out "{result.declined.title}". Here\'s another option:')
        _render_task(result.replacement)


@app.command()
def done(
    number: Annotated[int, typer.Argument(help="Task number from `youtopia today`.")],
    note: Annotated[str | None, typer.Option(help="A note about how it went.")] = None,
) -> None:
    """Mark a task as done."""
    with session_scope() as session:
        _require_profile(session)
        try:
            task = daily.complete_task(session, _today(), number, note)
        except daily.DailyError as err:
            console.print(f"[yellow]{err}[/yellow]")
            raise typer.Exit(code=1) from None
        console.print(f'[green]✓[/green] "{task.title}" done. Nice work.')


@app.command(name="stats")
def show_stats() -> None:
    """Show skill levels, recent history and milestones."""
    with session_scope() as session:
        _require_profile(session)
        result = stats.compute_stats(session, _today())

    skills = Table(title="Skills", title_justify="left")
    skills.add_column("Domain")
    skills.add_column("Level")
    skills.add_column("Completed", justify="right")
    for d in result.domains:
        level = f"{_level_dots(d.level)} {d.level}" if d.level else "-"
        skills.add_row(d.domain.capitalize(), level, str(d.completed))
    console.print(skills)

    console.print(
        f"[bold]{_plural(result.total_completed, 'task')}[/bold] done over "
        f"[bold]{_plural(result.active_days, 'active day')}[/bold] · "
        f"current streak {result.current_streak} · best {result.best_streak}"
    )
    console.print(f"[dim]Streaks forgive up to {stats.STREAK_GRACE_DAYS} days off in a row.[/dim]")

    if result.history:
        history = Table(title="Recent", title_justify="left")
        history.add_column("Date")
        history.add_column("Task")
        history.add_column("Domain")
        history.add_column("Note")
        for h in result.history:
            history.add_row(h.day.isoformat(), h.title, h.domain, h.note or "")
        console.print(history)

    if result.milestones:
        console.print("[bold]Milestones:[/bold] " + " · ".join(result.milestones))
    if result.next_milestone:
        console.print(f"[dim]Next: {result.next_milestone}[/dim]")
