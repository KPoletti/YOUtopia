---
title: AI providers
---

# AI providers

!!! warning "Planned for M5–M6"
    This page describes how AI generation *will* work. Today, every task comes from
    the built-in library, which keeps working offline after AI arrives.

Choose which benevolent intelligence assigns your jobs. YOUtopia works with **any model**,
and a small adapter layer speaks two dialects:

| Adapter | Covers |
| --- | --- |
| `anthropic` | Claude models, via the official Anthropic SDK |
| `openai_compat` | Anything that speaks the OpenAI chat-completions API: OpenAI, OpenRouter, Groq, Mistral, **Ollama**, **LM Studio**, vLLM, and your own server |

## Choose a provider

=== "Anthropic"

    ```bash
    youtopia config set ai.provider anthropic
    youtopia config set ai.model claude-haiku-5-5
    youtopia auth set anthropic          # paste your key; input is hidden
    youtopia ai test
    ```

=== "OpenAI-compatible"

    ```bash
    youtopia config set ai.provider openai      # or openrouter, groq, mistral, custom
    youtopia config set ai.model <model-id>     # any chat model your provider offers
    youtopia auth set openai
    youtopia ai test
    ```

=== "Fully local (Ollama)"

    ```bash
    ollama pull llama3.2
    youtopia config set ai.provider ollama      # http://localhost:11434/v1, no key needed
    youtopia config set ai.model llama3.2
    youtopia ai test
    ```

## API keys

Keys are looked up in this order, and the first one found wins:

1. `YOUTOPIA_API_KEY`
2. The provider's usual variable, such as `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`
3. Your OS keyring (service `youtopia`), set with `youtopia auth set <provider>`

Keys are **never** written to `config.toml` or the database, and never printed.
`youtopia auth status` shows only where a key came from and its last four characters.

!!! tip "No keyring? (headless Linux, WSL)"
    If no system keyring is available, `auth set` says so. Use an environment variable instead.

## What gets sent

Only what's needed to suggest good tasks: your interest areas, minutes per day,
accessibility limits, skill levels and recently offered task titles (so you don't get repeats).
**Your notes, history and anything identifying are never sent.**

## When your AI is on a break

No key, no network, a timeout, a slow model or unusable output: in every case
YOUtopia fills the gap from its built-in library, task by task. Generation never fails.
Use `youtopia today --offline` to skip AI entirely.
