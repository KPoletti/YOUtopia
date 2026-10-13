# YOUtopia

A terminal app that gives people purpose in a post-work, AI-abundant world by offering small, achievable daily tasks matched to their skills, and adapting difficulty as they grow.

The full requirements doc ("YOUtopia — Requirements") is the source of truth; this file is the build brief for the terminal MVP.

## Stack

- Python 3.12+, managed with `uv`
- Typer for commands, Rich for output
- SQLite at `~/.youtopia/youtopia.db` via SQLModel
- AI task generation through our own provider adapters, so any model works: Anthropic SDK, and OpenAI-compatible endpoints via `httpx` (OpenAI, OpenRouter, Ollama, LM Studio, …). Template tasks in `youtopia/templates.yaml` as fallback
- API keys from env vars or the OS keyring (`keyring`)
- pytest + ruff; docs site built with Zensical (`zensical.toml`, `docs/`)

## Layout

```
youtopia/
  cli.py            # Typer app and commands
  models.py         # SQLModel tables
  db.py             # engine/session, ~/.youtopia setup
  profile.py        # profile parsing, validation, saving
  daily.py          # daily loop: today, more, swap, done
  stats.py          # levels, history, streaks, milestones
  generator.py      # task generation: AI first, templates fallback
  templates.yaml    # built-in library: 70 LeetCode-style problems with hidden tests
  problems.py       # Problem (function, signature, tests) validation; starter files
  judge.py          # run a solution against hidden tests in a limited subprocess
  judge_harness.py  # the child process judge.py runs (stdlib only)
  difficulty.py     # adaptive difficulty rules
  support.py        # static help-now resources
  config.py         # ~/.youtopia/config.toml
  secrets.py        # API key lookup: env vars, then keyring
  providers/        # Provider protocol + adapters (anthropic, openai_compat, fake), registry
  safety.py         # safety filter for generated text
  terminal.py       # strip escape sequences, escape Rich markup
  usage.py          # daily AI-call cap
  encouragement.py  # messages from the tone sliders plus guilt
  phrases.yaml      # encouragement phrase bank
tests/
docs/               # Zensical docs site; roadmap.md has milestone detail
zensical.toml
```

## Commands

| Command | Behaviour |
| --- | --- |
| `youtopia init` | Onboarding: interests, minutes per day, accessibility limits, preferred challenge (1–5), tone sliders (default mix, or customise each). Under 5 minutes. |
| `youtopia today [--offline]` | Show today's tasks (a set of 3 to start); generate if none exist for today. |
| `youtopia more [N]` | Add N more tasks to today's list. No daily cap. |
| `youtopia swap <n>` | Decline task n, record the decline, offer a replacement. |
| `youtopia starter <n> [--out FILE]` | Write a solution skeleton for task n. |
| `youtopia submit <n> <file>` | Run the solution against task n's hidden tests; all passing completes it. |
| `youtopia done <n> [--note TEXT]` | Mark complete without tests (unverified), update skill level, print encouragement. |
| `youtopia stats` | Skill level per domain, history, milestones. |
| `youtopia profile` | View/edit profile, including tone sliders. |
| `youtopia help-now` | Print support and crisis resources. |
| `youtopia config show\|set` | View or change `config.toml` settings. |
| `youtopia auth set\|status\|remove` | Manage API keys in the OS keyring. |
| `youtopia ai test` | Check the configured provider answers. |

## Domain model

- **Profile**: interests, minutes_per_day, accessibility_limits, preferred_challenge, tone sliders `sincerity`, `humor`, `sarcasm`, `rudeness`, each 0–5 (default 4 / 1 / 0 / 0)
- **SkillLevel**: domain, level 1–5, recent_successes, recent_declines, recent_misses, last_evaluated
- **Task**: title, instructions, domain, difficulty 1–5, duration_minutes, done_criteria, offered_on, slot, status (`offered` | `done` | `declined`), source (`ai` | `template`), declined_at, problem (function, signature, tests, compare, tolerance)
- **Submission**: task_id, submitted_at, passed, total
- **Completion**: task_id, completed_at, note

Domains, named for the grunt work they are: labour, production, chores, outreach, training, caretaking, tickets (coding, maths and science problems). Old names (physical, creative, practical, social, learning, caring, problems) are accepted as input and migrated in stored data.

## Rules that must hold

- Every task is a LeetCode-style problem themed on its domain: statement, two examples, constraints, one Python function, hidden tests. Every template has a reference solution in `tests/reference_solutions.py`, and tests prove its hidden tests pass with it.
- `submit` evaluates by running hidden tests; passing all completes the task. Failed attempts are recorded but never penalised.
- Tasks fit the user's time and accessibility limits; never physically, legally or financially risky.
- Rotate domains across the daily set.
- Difficulty rises after consistent success and drops after repeated declines or misses. Thresholds live in `difficulty.py` as named constants.
- No penalties: missed days and declines never remove progress. Streaks forgive missed days.
- Guilt is part of every user's encouragement: a fixed `GUILT_WEIGHT` in `encouragement.py`, not a slider. Guilt nags about the tasks waiting and never insults the person.
- Encouragement blends the four tone sliders by weight, plus guilt. Sarcasm and rudeness tease the task, never the person. After several missed days or declines in a row it falls back automatically to sincere-only (sincerity 5, the rest 0, no guilt).
- Generation must work offline: on API error, no key or invalid output, use templates (per task).
- `today` opens with a set of 3; `more` adds any number on top, with no daily cap. AI calls stay capped by `ai.max_calls_per_day`.

### Security

- API keys come only from env vars or the OS keyring. Never store them in config or the DB, never print them (mask to last 4 at most), never log them.
- Send providers only the profile fields needed for generation. Never send notes or history.
- Strip escape sequences and escape Rich markup in all AI and user text before terminal output.
- Validate and safety-filter all AI output; anything that fails is replaced by a template.
- Remote provider URLs must use HTTPS; plain HTTP only for localhost.
- Never run AI-written code. AI problem signatures must match `problems.SIGNATURE_RE` (names and type hints only), and AI text only appears as comments in starter files.
- The judge runs user code with `-I`, an empty temp dir, a minimal environment (no API keys) and time/memory limits. It is not a sandbox, and the docs say so.
- CI workflows use least-privilege permissions and SHA-pinned actions.

## Milestones

Full steps, acceptance criteria and security checks: [docs/roadmap.md](docs/roadmap.md).

1. ✓ Scaffold, `init`, storage, tests.
2. ✓ Daily loop with templates only: `today`, `swap`, `done`, `stats`.
3. ✓ CI/CD for tests and docs (GitHub Actions, Pages).
4. ✓ Adaptive difficulty, `profile`, `help-now`.
5. ✓ Config, provider layer (any model), API keys.
6. ✓ AI task generation with validation, safety filter and template fallback.
7. ✓ Encouragement blended from the tone sliders, with automatic sincere fallback.
8. Security and privacy hardening.
9. Polish and release.

## Conventions

- Before calling a milestone done: `uv run pytest`, `uv run ruff check .`, `uv run zensical build --clean`, `uvx pip-audit`, plus the milestone's security checks.
- Update the docs pages that describe a feature in the same change; mark unreleased features with a "Arrives in Mx" admonition.
- Keep business logic out of `cli.py`; it should only parse input and render output.
- Tests use a temporary database, never `~/.youtopia`.