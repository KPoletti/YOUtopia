---
title: AI providers
---

# AI providers

Choose which benevolent intelligence assigns your jobs. YOUtopia works with **any model**,
and a small adapter layer speaks two dialects:

| Adapter | Covers |
| --- | --- |
| `anthropic` | Claude models, via the official Anthropic SDK |
| `openai_compat` | Anything that speaks the OpenAI chat-completions API: OpenAI, OpenRouter, Groq, Mistral, **Ollama**, **LM Studio**, vLLM, and your own server |

AI is **off** until you turn it on. Without it, every task comes from the built-in library.

## Choose a provider

=== "Anthropic"

    ```bash
    youtopia config set ai.provider anthropic
    youtopia config set ai.model claude-haiku-5-5   # optional; defaults to claude-opus-5-5
    youtopia auth set anthropic          # paste your key; input is hidden
    youtopia ai test
    youtopia config set ai.enabled true
    ```

=== "OpenAI-compatible"

    ```bash
    youtopia config set ai.provider openai      # or openrouter, groq, mistral
    youtopia config set ai.model <model-id>     # any chat model your provider offers
    youtopia auth set openai
    youtopia ai test
    youtopia config set ai.enabled true
    ```

=== "Fully local (Ollama)"

    ```bash
    ollama pull llama3.2
    youtopia config set ai.provider ollama      # http://localhost:11434/v1, no key needed
    youtopia config set ai.model llama3.2
    youtopia ai test
    youtopia config set ai.enabled true
    ```

=== "Your own server"

    ```bash
    youtopia config set ai.provider custom
    youtopia config set ai.base_url https://llm.example.com/v1
    youtopia config set ai.model my-model
    youtopia ai test
    youtopia config set ai.enabled true
    ```

Ready-made URLs: `openai`, `openrouter`, `groq` and `mistral` use their official HTTPS
endpoints, `ollama` uses `http://localhost:11434/v1` and `lmstudio` uses
`http://localhost:1234/v1`. Set `ai.base_url` to override any of them.

## Settings

All settings live in `~/.youtopia/config.toml` (readable only by you). Change them with
`youtopia config set KEY VALUE` and view them with `youtopia config show`.

| Key | Default | Meaning |
| --- | --- | --- |
| `ai.enabled` | `false` | Use AI for tasks at all |
| `ai.provider` | `anthropic` | One of `anthropic`, `openai`, `openrouter`, `groq`, `mistral`, `ollama`, `lmstudio`, `custom` |
| `ai.model` | provider default | Model ID. Required for every provider except `anthropic` |
| `ai.base_url` | provider default | Endpoint URL. Must be HTTPS, except on `localhost` |
| `ai.timeout_s` | `20` | Seconds before a request gives up (1–300) |
| `ai.max_calls_per_day` | `20` | Daily cap on AI calls (0–1000). Past it, tasks come from the library |
| `ai.reword_encouragement` | `false` | Let the model reword `done` messages, within the same safety checks |

## API keys

Keys are looked up in this order, and the first one found wins:

1. `YOUTOPIA_API_KEY`
2. The provider's usual variable, such as `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`
3. Your OS keyring (service `youtopia`), set with `youtopia auth set <provider>`

Keys are **never** written to `config.toml` or the database, and never printed.
`youtopia auth status` shows only where a key came from and its last four characters.
Error messages from providers are scrubbed of keys and `Authorization` headers.

!!! tip "No keyring? (headless Linux, WSL)"
    If no system keyring is available, `auth set` says so. Use an environment variable instead.

## What gets sent

Only what's needed to suggest good tasks: your interest areas, minutes per day,
accessibility limits, skill levels, the areas and levels wanted, and recently offered task
titles (so you don't get repeats). Free text goes inside a clearly marked data block,
cleaned and capped at 200 characters per item, and the model is told to treat it as data.
**Your notes, history and anything identifying are never sent.**

## How AI tasks are checked

Each suggestion is checked on its own, and anything that fails is swapped for a built-in
task in that slot:

- **Format:** valid JSON in the expected shape, a known area, difficulty 1–5, and length limits.
- **Problem:** a valid function name and a one-line signature with only names and type
  hints, plus 3–12 hidden tests made of plain JSON values. AI-written tests can't be
  checked against a reference solution (that would mean running model-written code), so
  `submit` notes when the tests came from AI.
- **Fit:** no longer than your minutes per day, and nothing your accessibility limits rule out,
  whether or not the model tagged it.
- **Safety:** a filter rejects risky themes (heights, fire, fasting, extreme exertion, money,
  trespass, alcohol and drugs, strangers' homes and more).
- **Variety:** no repeats of today's tasks or recent ones.

Text is stripped of terminal escape codes and formatting markup before it's shown.

## Costs and limits

- One AI call per daily set, one per swap and one per `youtopia more`.
- `ai.max_calls_per_day` caps the total (20 by default).
- Requests time out after `ai.timeout_s`, and a timeout or server error is retried once.

## When your AI is on a break

No key, no network, a timeout, a slow model or unusable output: in every case
YOUtopia fills the gap from its built-in library, task by task, with one dim note saying
why. Generation never fails. Use `--offline` on `today`, `swap`, `more` or `done` to skip AI
entirely.
