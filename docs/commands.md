---
title: Commands
---

# Commands

The official ways to accept your AI's generosity. Run `youtopia <command> --help` for full options.

## Available now

### `youtopia init`

Create or update your profile. It prompts for anything not given as a flag.

| Flag | Meaning |
| --- | --- |
| `--interests TEXT` | Comma-separated areas (`labour`, `production`, `chores`, `outreach`, `training`, `caretaking`, `tickets`) or `all`. The old names (`physical`, `creative`, …) still work. |
| `--minutes N` | Minutes you can spare per day |
| `--accessibility TEXT` | Comma-separated limits, or `none` |
| `--challenge 1-5` | Preferred challenge |
| `--sincerity`, `--humor`, `--sarcasm`, `--rudeness 0-5` | [Tone sliders](tone.md); any you leave out keep their defaults |
| `--yes`, `-y` | Update an existing profile without asking |

### `youtopia today [--offline]`

Receive today's assignments: a fresh set of three, if none have been issued yet, with a
one-line greeting in your [tone](tone.md). Each task shows its area, difficulty (`●●○○○`),
duration and how you'll know it's done. When [AI is on](ai-providers.md), tasks are
written for you; `--offline` uses only the built-in library.

### `youtopia more [N] [--offline]`

Add `N` more tasks to today's list (default 1). There's no daily limit: ask as often as
you like. The only ceiling is what fits your time and limits, plus your daily AI-call cap
(extras past it come from the built-in library).

### `youtopia swap N`

Decline task `N` and get a replacement in the same slot, usually from a different area
(`--offline` skips AI for the replacement).
Declines are recorded so YOUtopia can learn what suits you, and never count against you. It said it's fine. It meant it.

### `youtopia done N [--note TEXT]`

Mark task `N` as complete, with an optional note for your history (or a thank-you, if
you're feeling generous). You get a message blended from your [tone sliders](tone.md),
with a little guilt included for everyone.

### `youtopia stats`

Your performance review, minus the anxiety: your level in each area, recent completions,
total active days, your current and best streak, and the milestones you've reached.

### How levels adapt

Each area has its own level, from 1 to 5, and today's tasks are matched to it.

- **Up:** three completions at or above your level in an area raise it by one.
- **Eased:** three swaps, or three tasks left unfinished on past days, ease it by one.
  A completion clears those counts, and days with no tasks never count.
- Levels stay between 1 and 5. Completions, streaks and milestones are never touched,
  so easing only changes what you're offered, never what you've done.

### `youtopia profile [--edit [FIELD]]`

Show your profile. With `--edit`, answer the onboarding questions again with your
current answers as defaults; add a field (`interests`, `minutes`, `accessibility`,
`challenge` or `tone`) to change just that one. Levels and history are always kept.

```bash
youtopia profile --edit tone
```

### `youtopia help-now`

Support and crisis resources: emergency numbers, helplines and
[findahelpline.com](https://findahelpline.com). Works offline and without a profile, never uses AI.

### `youtopia config show` / `youtopia config set KEY VALUE`

View or change settings in `~/.youtopia/config.toml`, such as `ai.enabled`, `ai.provider`
and `ai.model`. See [AI providers](ai-providers.md#settings) for every key.
API keys are never stored there.

### `youtopia auth set|status|remove PROVIDER`

`set` stores a key in your OS keyring (input is hidden). `status` shows where each key
comes from and at most its last four characters. `remove` deletes it from the keyring.

### `youtopia ai test`

Sends one tiny prompt to your configured provider and reports the provider, model and
response time.

## Coming soon

!!! note "Arrives in M8–M9"
    - `youtopia data export` and `youtopia data delete`: take your data with you, or erase it completely.
    - `youtopia doctor`: check that everything is healthy.
