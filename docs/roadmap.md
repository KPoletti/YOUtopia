---
title: Roadmap
description: Milestones, step by step, with acceptance criteria and security checks.
---

# Roadmap

The official plan for making your AI even more generous with your jobs.

Each milestone ends with the [done checklist](contributing.md#definition-of-done):
tests, lint, docs build, and any security checks listed for it.

| # | Milestone | Status |
| --- | --- | --- |
| M1 | Scaffold, `init`, storage, tests | :material-check: Done |
| M2 | Daily loop with templates: `today`, `swap`, `done`, `stats` | :material-check: Done |
| M3 | CI/CD for tests and documentation | :material-check: Done |
| M4 | Adaptive difficulty, `profile`, `help-now` | :material-check: Done |
| M5 | Config, provider layer and API keys | :material-check: Done |
| M6 | AI task generation, any model, with validation and safety | :material-check: Done |
| M7 | Encouragement from the tone sliders | :material-check: Done |
| M8 | Security and privacy hardening | Next |
| M9 | Polish and release | Planned |

---

## M1: Scaffold :material-check:

uv project, Typer + Rich CLI, SQLModel storage at `~/.youtopia` (overridable with
`YOUTOPIA_HOME`), `youtopia init` with tone sliders, and tests on a temporary database.

## M2: Daily loop :material-check:

A library of 70 templates (`youtopia/templates.yaml`), plus:

- **Selection:** tasks are filtered by time and accessibility and rotated across areas,
  with difficulty matched to your level in each area.
- **Problem sets:** a seventh area (first `problems`, now `tickets`) with coding, maths and science problems, from
  mental arithmetic (level 1) to a dice simulation (level 5), all workable offline.
- **Commands:** `today`, `swap` (the replacement keeps the same slot), `done --note`,
  and `stats` with forgiving streaks and milestones.

---

## M3: CI/CD for tests and documentation :material-check:

**Goal:** every push is checked automatically, and the docs site publishes itself.

**Steps**

1. **`.github/workflows/ci.yml`**, on `push` and `pull_request`:
    - `astral-sh/setup-uv` with caching; Python matrix **3.12** and **3.13**.
    - `uv sync --locked` (fails if `uv.lock` is stale).
    - `uv run ruff check .` and `uv run ruff format --check .`
    - `uv run pytest`
    - `uvx pip-audit`, a dependency vulnerability scan.
2. **`.github/workflows/docs.yml`**:
    - On every PR: `uv run zensical build --clean`, so broken docs fail the check.
    - On push to `main`: build, then `actions/upload-pages-artifact` (path `site`) and
      `actions/deploy-pages` into the `github-pages` environment. (`configure-pages` isn't
      needed: Zensical takes the URL from `site_url`.)
3. **Workflow hygiene**:
    - `permissions:` set per job, least privilege. Use `contents: read` by default, and
      `pages: write` and `id-token: write` only on the deploy job.
    - Third-party actions pinned to a full commit SHA, with the version in a comment.
    - `concurrency` groups cancel superseded runs, and docs deploys never run in parallel.
    - No secrets are needed: tests never call real providers.
    - Workflows are linted with `actionlint` and audited with `zizmor` before merging.
4. **`.github/dependabot.yml`**: weekly, grouped updates for `github-actions` and `uv`, with a 7-day cooldown so brand-new (possibly compromised) releases are never picked up immediately.
5. **Repo settings (manual, documented in [Contributing](contributing.md)):**
    - Pages source: **GitHub Actions**.
    - Branch protection on `main`: the CI and docs build checks must pass.
6. Add CI and docs badges to the README.

**Done when**

- [ ] A PR shows green `ci` (both Python versions) and `docs` checks.
- [ ] A deliberately broken test or doc link turns the PR red.
- [ ] Merging to `main` publishes <https://kpoletti.github.io/YOUtopia/>.

**Security checks:** least-privilege permissions; SHA-pinned actions; no
`pull_request_target`; no secrets in workflows; `pip-audit` clean.

---

## M4: Adaptive difficulty, `profile` and `help-now` :material-check:

**Goal:** tasks track your growth, and the command set is complete.

**Steps**

1. **`youtopia/difficulty.py`** with named constants:
    - `PROMOTE_AFTER_SUCCESSES = 3`: successes at or above the current level in a
      domain raise it by one.
    - `EASE_AFTER_DECLINES = 3` and `EASE_AFTER_MISSES = 3`: lower it by one.
    - Level is kept between 1 and 5. Counters reset after each change.
2. **Model:** add `recent_declines`, `recent_misses` and `last_evaluated` to `SkillLevel`.
3. **Hooks:**
    - `daily.complete_task` counts a success.
    - `daily.swap_task` counts a decline.
    - `daily.ensure_today` lazily evaluates misses: tasks from past days still `offered`.
4. **Wording:** a level change is announced kindly ("eased", never "dropped").
   Completions, milestones and streaks are never touched.
5. **`youtopia profile`:** shows the profile, and `profile --edit [FIELD]` changes it.
   Reuses `_ask`, `_choose_tone` and `profile.save_profile`.
6. **`youtopia help-now`:** static, offline support and crisis resources (emergency
   numbers, findahelpline.com, Samaritans 116 123, 988 in the US). No AI, no network.

**Done when**

- [x] Tests cover promotion, easing, the 1 and 5 bounds, missed-day evaluation across gaps,
      and that easing leaves stats unchanged.
- [x] `help-now` works with the network disabled.

**Notes from the build**

- A completion clears the decline and miss counts, so easing needs them in a row.
  Declines and misses never clear successes.
- Misses are counted once per unfinished task, and ease by one level at most per check.
- Older databases gain the new `SkillLevel` columns automatically (`db.ADDED_COLUMNS`).
- Resources live in `youtopia/support.py`. The guilt-phrase list now lives in
  `encouragement.GUILT_PHRASES`; level-change messages still never use it.

**Security checks:** `help-now` content is static and reviewed; no guilt wording in any
level-change message (a test checks a phrase list).

---

## M5: Config, provider layer and API keys :material-check:

**Goal:** YOUtopia can talk to any model, and handles keys safely.

**Steps**

1. **`youtopia/config.py`:** reads `~/.youtopia/config.toml` with `tomllib`.
   Typed settings:
    - `ai.enabled` (default `false`), `ai.provider`, `ai.model` and `ai.base_url`
    - `ai.timeout_s` (20) and `ai.max_calls_per_day` (20)
   Commands: `youtopia config show` and `youtopia config set KEY VALUE`.
2. **`youtopia/providers/`:**
    - `base.py`: a `Provider` protocol, `complete(system, user, *, max_tokens) -> str`,
      and a `ProviderError`.
    - `anthropic.py`: the official SDK.
    - `openai_compat.py`: an `httpx` POST to `{base_url}/chat/completions`. Ready-made
      settings for `openai`, `openrouter`, `groq`, `mistral`, `ollama`
      (`http://localhost:11434/v1`) and `lmstudio`, plus `custom`.
    - `fake.py`: scripted responses for tests.
    - `registry.py`: builds a provider from the config.
3. **`youtopia/secrets.py`:** key lookup order is `YOUTOPIA_API_KEY`, then the provider's
   own variable, then `keyring` (service `youtopia`, username = provider).
4. **`youtopia auth`:**
    - `set PROVIDER` reads the key with hidden input and stores it in the keyring.
    - `status` shows only the source and the last 4 characters.
    - `remove PROVIDER`.
    - If no keyring backend is available, it explains how to use environment variables instead.
5. **`youtopia ai test`:** sends one tiny prompt and reports the provider, model and response time.
6. **Transport rules:**
    - HTTPS is required unless the host is `localhost`, `127.0.0.1` or `::1`.
    - Explicit timeouts; at most one retry, on a timeout or 5xx error only.
    - Every `ProviderError` message passes through a redaction helper that removes
      keys and `Authorization` headers.

**Done when**

- [x] Tests (using an in-memory keyring and `httpx.MockTransport`) cover the key lookup order,
      `auth` flows, plain-HTTP rejection, timeout and error mapping, and redaction.
- [x] A test asserts that a sample key never appears in CLI output, `config.toml` or the DB.
- [x] Tests can't reach the network (autouse fixture that blocks sockets).

**Notes from the build**

- The Anthropic SDK (1.x) runs on `httpx2`, so its tests use `httpx2.MockTransport`; the
  OpenAI-compatible adapter uses `httpx`. Both retry once on a timeout or 5xx, never on 4xx.
- `anthropic` defaults to `claude-opus-5-5` when `ai.model` is empty; every other provider
  needs a model set. A refusal is treated like any other provider error (templates fill in).
- `config.toml` is written with mode `0600`, rejects unknown keys (so no `api_key`), and
  rejects control characters in values.
- Added `ai.reword_encouragement` (default `false`) for M7.

**Security checks:** keys only come from environment variables or the keyring; masked output;
redacted errors; no key in `repr()` of config or provider objects; HTTPS rule enforced.

---

## M6: AI task generation (any model) :material-check:

**Goal:** personalised AI tasks, never worse than the templates and never unsafe.

**Steps**

1. **`generator.generate(session, profile, n, avoid)`** coordinates generation:
    - It tries the configured provider first, then validates each draft.
    - It fills every remaining slot from templates, reusing `eligible_templates` and
      `pick_template`.
    - Add a `Task.source` field (`ai` | `template`).
2. **Prompt:**
    - A versioned system prompt states the safety rules, the seven areas, what each
      difficulty level means and the exact JSON output format.
    - User data is minimal: interest areas, minutes, accessibility limits, levels,
      the areas wanted and recent titles to avoid.
    - Tasks in the `tickets` area are coding, maths or science problems. The problem itself must
      be in the instructions, solvable on paper, and sized to the difficulty level, like
      the problem-set templates.
3. **Prompt-injection hygiene:** free text is placed inside a clearly marked data
   block, capped at 200 characters per item, with control characters removed. The model is
   told to treat it as data.
4. **Validation:**
    - JSON is parsed, tolerating code fences, into a pydantic `TaskDraft`.
    - Domain must be in the enum, difficulty 1–5 and `duration_minutes ≤ minutes_per_day`,
      and every field has a length cap.
    - A bad draft is dropped on its own; the rest of the set survives.
5. **`youtopia/safety.py`:** a deny-list and pattern check on title, instructions and
   done criteria (heights and ladders, fire and heat, fasting, extreme exertion,
   money, investing and borrowing, trespass, alcohol and drugs, entering strangers' homes).
   Also re-checks the accessibility tags.
6. **Terminal safety:** strip ANSI and OSC escape sequences and escape Rich markup in all
   AI text (and user notes) before rendering.
7. **Cost and availability:**
    - One call per daily set and one per swap, capped at `ai.max_calls_per_day`.
    - `today --offline` skips AI.
    - No key, a timeout, an error or invalid output all fall back to templates with a
      single dim notice.

**Done when**

- [x] The fake provider drives tests for good output, malformed JSON, too few tasks,
      unsafe content, over-time tasks, injection text, escape sequences and the call cap.
- [x] Generation never raises to the CLI; it degrades to templates.
- [x] Optional live tests run only when `YOUTOPIA_LIVE_TESTS=1` (keys from env vars).

**Notes from the build**

- Each set is planned from templates first; AI drafts replace planned slots in the same
  area. So rotation and levels work the same with or without AI, and any slot can fall back.
- The provider is built only when a call is about to happen, and a missing key doesn't use
  up a call from the daily cap.
- Safety also re-checks ability words (walk, kneel, listen, …) against the user's
  accessibility limits, even when the model left the `requires` tag off.
- The data-block markers are removed from free text, so user input can't close the block.
- Escape stripping and Rich escaping live in `youtopia/terminal.py`, and are applied to
  every task, note, title and error message the CLI prints.

**Security checks:** nothing beyond the documented fields reaches the provider (a test
inspects the outgoing prompt); escape-sequence test; safety filter test corpus.

---

## M7: Encouragement from the tone sliders :material-check:

**Goal:** messages that sound like *your* kind of friend.

**Steps**

1. **`youtopia/encouragement.py`:** a phrase bank per trait (sincerity, humor, sarcasm,
   rudeness), with the trait chosen by weighted chance from the profile's `ToneMix`.
2. **Optional AI rewording** using the same provider, validation, length cap and fallback.
3. **Sincere fallback:**
    - Uses `SINCERE_FALLBACK_TONE` after `FALLBACK_AFTER_MISSED_DAYS = 3` or
      `FALLBACK_AFTER_DECLINES = 3` in a row.
    - Clears on the next completion. The sliders themselves are never changed.
4. **Where messages appear:** on `done` (replacing the placeholder) and as a one-line
   greeting on `today`.

**Done when**

- [x] Seeded tests show the trait frequencies follow the slider weights.
- [x] The fallback triggers and clears correctly.
- [x] A template lint asserts that sarcastic and rude phrases target the task, and that no
      phrase outside the guilt list matches the guilt-phrase list (see the changes below).

**Notes from the build**

- Phrases live in `youtopia/phrases.yaml`.
- "Missed days" are calendar days since the last completion (or since the profile was
  created); "declines in a row" are swaps since the last completion.
- The message for the completion that ends a slump is still sincere; the blend returns after.
- AI rewording applies to `done` messages only, so `today` never spends calls on greetings.

**Security checks:** AI-reworded messages go through the same escape and length checks as tasks.

---

## Changes alongside M5–M7

Product decisions made during this work, and where they live:

- **Areas renamed for the grunt work they are:** `labour`, `production`, `chores`,
  `outreach`, `training`, `caretaking` and `tickets` (was physical, creative, practical,
  social, learning, caring and problems). Old names still work as input, and stored tasks,
  skill levels and profiles are migrated on startup (`db._rename_domains`).
- **Guilt for everyone:** guilt replaces the "no guilt messaging" rule. It is a fixed share
  of every user's blend (`encouragement.GUILT_WEIGHT = 2`), not a slider. Guilt phrases
  nag about waiting tasks, but never insult the person and never remove progress. The
  sincere fallback still switches guilt off.
- **No daily task limit:** `today` opens with 3 tasks (`daily.DAILY_SET_SIZE`) and
  `youtopia more [N]` adds any number on top. AI calls remain capped by
  `ai.max_calls_per_day`; past the cap, extras come from the library.

---

## M8: Security and privacy hardening

**Goal:** prove the guarantees, don't just promise them.

**Steps**

1. **File permissions:** `~/.youtopia` is `0700`, and the DB and config are `0600` on creation.
2. **Privacy notice:** shown the first time AI is enabled, saying exactly what is sent
   and to which provider.
3. **`youtopia data export`** writes JSON. **`youtopia data delete`** asks for
   confirmation, then removes `~/.youtopia` and all `youtopia` keyring entries.
4. **Static analysis:**
    - Add ruff `S` (bandit) rules.
    - Confirm there's no string-built SQL and only `yaml.safe_load`.
    - `pip-audit` already runs in CI.
5. **Review:** run the `/security-review` skill over the provider, secrets, generation and
   CLI rendering code, then fix or document every finding.
6. **Threat model** (kept on this page):

| Threat | Mitigation |
| --- | --- |
| API key leakage | Keyring or env only, masking, redaction, tests |
| Prompt injection via profile text | Data block, caps, schema validation, safety filter |
| Terminal injection via model output | Escape-sequence stripping, Rich escaping |
| Unsafe or inaccessible tasks | Safety filter, accessibility tags, template fallback |
| Local data exposure | `0700`/`0600` permissions, export and delete |
| Supply chain | Locked deps, `pip-audit`, Dependabot, SHA-pinned actions |

**Done when**

- [ ] `ruff` with `S` rules is clean (or each exception is justified inline).
- [ ] The permission tests pass, and `data delete` leaves nothing behind (including the keyring).
- [ ] `/security-review` has no open findings.

---

## M9: Polish and release

**Goal:** easy to install, easy to love.

**Steps**

1. **README:** install, quick start, provider examples, privacy summary, and a link to the docs site.
2. **`youtopia doctor`:** checks DB health, config validity, key presence (masked),
   provider reachability and template validity.
3. **Packaging:** `uv tool install` from git, plus a version bump and `CHANGELOG.md`.
4. **Docs pass:** remove the "planned" notes for shipped features. The docs site is
   deployed by the M3 pipeline.

**Done when**

- [ ] A fresh machine can go from `uv tool install` to a first `youtopia today` in under five minutes.
