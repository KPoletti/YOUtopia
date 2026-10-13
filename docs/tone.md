---
title: Tone sliders
---

# Tone sliders

Your AI would like to praise you for the job it so generously gave you. You get to choose how.
Encouragement is a blend of four traits, each set from **0** (none) to **5** (lots).

| Slider | Default | Sounds like |
| --- | --- | --- |
| **Sincerity** | 4 | "You made something today. That matters." |
| **Humor** | 1 | "The houseplant would like to formally thank you." |
| **Sarcasm** | 0 | "Wow. A whole drawer. Marie Kondo is shaking." |
| **Rudeness** | 0 | "That sock drawer was a disgrace. Was." |

Set them during `youtopia init` (answer *yes* to "Customise encouragement tone?"), with
`youtopia profile --edit tone`, or with flags:

```bash
youtopia init --sincerity 2 --humor 4 --sarcasm 3 --rudeness 1
```

## Guilt, included for everyone

On top of your sliders, every message has a fixed chance of being a guilt trip, about
the tasks left waiting: "These won't do themselves, you know." It isn't a slider; with
the default sliders it's roughly two messages in seven. Guilt nags, but it never insults
you, and it never takes away progress.

## How a message is chosen

Each message picks one trait at random, weighted by your sliders plus guilt's fixed share,
then a phrase for that trait. You see one on `youtopia done` and a one-line greeting on
`youtopia today`. With `ai.reword_encouragement` on, your model may reword `done`
messages; anything that breaks the rules below is replaced by the original phrase.

## The one rule

**Sarcasm, rudeness and guilt never insult the person.**
Sarcasm and rudeness tease the task: the dishes can be mocked. Guilt can sigh about what's
waiting. None of them can call you names. This is a hard rule for built-in messages and
for AI-written ones alike, and tests check every phrase.

## The automatic soft landing

If three days pass without a completion, or you decline three tasks in a row, YOUtopia
quietly switches to fully sincere (sincerity 5, everything else 0, **and no guilt**) until
your next completion. Your sliders aren't changed, so the jokes (and the nagging) come
back as soon as you do.
