---
title: Getting started
---

# Getting started

Congratulations! Your AI has kindly found you a job. Here's how to accept it.

## Install

YOUtopia needs Python 3.12+ and [uv](https://docs.astral.sh/uv/).

=== "As a tool"

    ```bash
    uv tool install git+https://github.com/KPoletti/YOUtopia
    youtopia --help
    ```

=== "From a clone"

    ```bash
    git clone https://github.com/KPoletti/YOUtopia
    cd YOUtopia
    uv sync
    uv run youtopia --help
    ```

Your data lives in `~/.youtopia/youtopia.db`. Set `YOUTOPIA_HOME` to keep it somewhere else.

## Your job interview

```bash
youtopia init
```

A handful of questions, well under five minutes. Don't worry, you've already got the job:

| Question | Example | Why |
| --- | --- | --- |
| Interests | `creative, learning` or `all` | Which of the seven areas to draw tasks from |
| Minutes per day | `20` | No task will ever be longer |
| Accessibility limits | `no kneeling, low vision` or `none` | Tasks that need these are never offered |
| Preferred challenge | `1` (gentle) to `5` (stretch) | Your starting level in every area |
| Tone | keep the default, or customise | See [Tone sliders](tone.md) |

Every answer can also be given as a flag, which is handy for scripts:

```bash
youtopia init --interests all --minutes 20 --accessibility none --challenge 2 --humor 3
```

Running `init` again updates your profile. Your progress is always kept. HR never forgets (in a good way).

## Your daily shift

```bash
youtopia today            # see today's three tasks
youtopia swap 2           # not feeling task 2? get another, no questions asked
youtopia done 1           # finished task 1
youtopia done 3 --note "harder than it looked"
youtopia stats            # levels, recent history, streaks and milestones
```

`today` always shows the same set for the rest of the day, so check back as often as you like. Your assignments won't change behind your back.

!!! tip "Skipping is fine (really)"
    Didn't get to anything today? That's allowed. Tomorrow brings a fresh set,
    and your streak forgives up to two days off in a row.
