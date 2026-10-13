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
| M4 | Adaptive difficulty, `profile`, `help-now` | Next |
| M5 | Config, provider layer and API keys | Planned |
| M6 | AI task generation, any model, with validation and safety | Planned |
| M7 | Encouragement from the tone sliders | Planned |
| M8 | Security and privacy hardening | Planned |
| M9 | Polish and release | Planned |

---

## M1: Scaffold :material-check:

uv project, Typer + Rich CLI, SQLModel storage at `~/.youtopia` (overridable with
`YOUTOPIA_HOME`), `youtopia init` with tone sliders, and tests on a temporary database.

## M2: Daily loop :material-check:

A library of 60 templates (`youtopia/templates.yaml`), plus:

- **Selection:** tasks are filtered by time and accessibility and rotated across areas,
  with difficulty matched to your level in each area.
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

## M4: Adaptive difficulty, `profile` and `help-now`

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

- [ ] Tests cover promotion, easing, the 1 and 5 bounds, missed-day evaluation across gaps,
      and that easing leaves stats unchanged.
- [ ] `help-now` works with the network disabled.

**Security checks:** `help-now` content is static and reviewed; no guilt wording in any
level-change message (a test checks a phrase list).

---

## M5: Config, provider layer and API keys

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

- [ ] Tests (using an in-memory keyring and `httpx.MockTransport`) cover the key lookup order,
      `auth` flows, plain-HTTP rejection, timeout and error mapping, and redaction.
- [ ] A test asserts that a sample key never appears in CLI output, `config.toml` or the DB.
- [ ] Tests can't reach the network (autouse fixture that blocks sockets).

**Security checks:** keys only come from environment variables or the keyring; masked output;
redacted errors; no key in `repr()` of config or provider objects; HTTPS rule enforced.

---

## M6: AI task generation (any model)

**Goal:** personalised AI tasks, never worse than the templates and never unsafe.

**Steps**

1. **`generator.generate(session, profile, n, avoid)`** coordinates generation:
    - It tries the configured provider first, then validates each draft.
    - It fills every remaining slot from templates, reusing `eligible_templates` and
      `pick_template`.
    - Add a `Task.source` field (`ai` | `template`).
2. **Prompt:**
    - A versioned system prompt states the safety rules, the six areas, what each
      difficulty level means and the exact JSON output format.
    - User data is minimal: interest areas, minutes, accessibility limits, levels,
      the areas wanted and recent titles to avoid.
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

- [ ] The fake provider drives tests for good output, malformed JSON, too few tasks,
      unsafe content, over-time tasks, injection text, escape sequences and the call cap.
- [ ] Generation never raises to the CLI; it degrades to templates.
- [ ] Optional live tests run only when `YOUTOPIA_LIVE_TESTS=1`.

**Security checks:** nothing beyond the documented fields reaches the provider (a test
inspects the outgoing prompt); escape-sequence test; safety filter test corpus.

---

## M7: Encouragement from the tone sliders

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

- [ ] Seeded tests show the trait frequencies follow the slider weights.
- [ ] The fallback triggers and clears correctly.
- [ ] A template lint asserts that sarcastic and rude phrases target the task, and that no
      phrase anywhere matches the guilt-phrase list.

**Security checks:** AI-reworded messages go through the same escape and length checks as tasks.

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
