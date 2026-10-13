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
| `--interests TEXT` | Comma-separated areas (`physical`, `creative`, `practical`, `social`, `learning`, `caring`) or `all` |
| `--minutes N` | Minutes you can spare per day |
| `--accessibility TEXT` | Comma-separated limits, or `none` |
| `--challenge 1-5` | Preferred challenge |
| `--sincerity`, `--humor`, `--sarcasm`, `--rudeness 0-5` | [Tone sliders](tone.md); any you leave out keep their defaults |
| `--yes`, `-y` | Update an existing profile without asking |

### `youtopia today`

Receive today's assignments: a fresh set of up to three, if none have been issued yet.
Each task shows its area, difficulty (`●●○○○`), duration and how you'll know it's done.

### `youtopia swap N`

Decline task `N` and get a replacement in the same slot, usually from a different area.
Declines are recorded so YOUtopia can learn what suits you, and never count against you. It said it's fine. It meant it.

### `youtopia done N [--note TEXT]`

Mark task `N` as complete, with an optional note for your history (or a thank-you, if you're feeling generous).

### `youtopia stats`

Your performance review, minus the anxiety: your level in each area, recent completions,
total active days, your current and best streak, and the milestones you've reached.

## Coming soon

!!! note "Arrives in M4"
    - `youtopia profile`: view or edit a single profile field, including tone sliders.
    - `youtopia help-now`: support and crisis resources, available instantly and offline.

!!! note "Arrives in M5"
    - `youtopia config show` and `youtopia config set KEY VALUE`: choose an AI provider and model.
    - `youtopia auth set|status|remove PROVIDER`: manage API keys in your OS keyring.
    - `youtopia ai test`: check that your model answers.

!!! note "Arrives in M8–M9"
    - `youtopia data export` and `youtopia data delete`: take your data with you, or erase it completely.
    - `youtopia doctor`: check that everything is healthy.
