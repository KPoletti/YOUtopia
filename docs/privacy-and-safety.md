---
title: Privacy & safety
---

# Privacy & safety

Your AI employer is generous, but it is not nosy. This page is the boring, important
fine print, and it's written straight.

## What's stored, and where

| What | Where | Leaves your machine? |
| --- | --- | --- |
| Profile, tasks, completions, notes | `~/.youtopia/youtopia.db` | Never |
| Settings (provider, model) | `~/.youtopia/config.toml` | Never |
| API keys | OS keyring or your environment | Only to the provider you chose, to authenticate |

The data folder is readable only by you (permissions `0700`, files `0600`).
`youtopia data export` and `youtopia data delete` (coming in M8) let you take everything
with you or erase it, keyring entries included.

## What's sent to an AI provider

Only when AI is turned on, and only the minimum needed: interest areas, minutes per day,
accessibility limits, skill levels and recent task titles. Never notes, history,
or anything that identifies you. A local model (Ollama, LM Studio) keeps even that on your machine.

## Every task is safe

Tasks must never be physically, legally or financially risky. For the built-in library,
that's a review rule. For AI-written tasks it's enforced in code:

- Output is checked against a strict format. Wrong area, a difficulty out of range,
  or a task longer than your daily time all mean it's rejected.
- A safety filter rejects risky themes: heights, fire, fasting, extreme exertion,
  money and investing, trespassing, alcohol and drugs.
- Your accessibility limits are always respected, and never relaxed to fill a slot.
- Anything rejected is replaced by a safe built-in task.

## Your terminal is safe too

Text from a model, or anything you type, is cleaned of terminal escape codes
before it's displayed, so nothing can mess with your terminal.

## When you need more than a task

```bash
youtopia help-now
```

This shows support and crisis resources instantly. It works offline and never involves AI.

!!! danger "If you are in immediate danger"
    Call your local emergency number now (112 in the EU, 911 in the US, 999 in the UK).
    You can find a free, confidential helpline in your country at
    [findahelpline.com](https://findahelpline.com).
