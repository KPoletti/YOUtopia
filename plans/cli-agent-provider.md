# Plan: use a model subscription through its official CLI (`cli_agent` provider)

Branch: `claude/cli-agent-provider` (from `main` at #4). Status: not started.

## Goal

Let people use a model subscription they already pay for (Claude Pro/Max first) instead of
an API key. YOUtopia runs the provider's own CLI, which the user has logged into, as a
subprocess. YOUtopia never sees or stores a credential.

Don't extract subscription OAuth tokens and call the API directly; the providers reserve
those logins for their own tools.

## Scope

- **In:** Claude Code (`claude -p`). Its docs show how to turn every tool off (below).
- **Out for now:**
  - Codex CLI (`codex exec`): its docs show no way to disable the shell tool entirely
    (`--sandbox read-only` restricts commands but doesn't remove them).
  - Gemini CLI: no documented way to turn off all built-in tools, and it was replaced by
    Antigravity CLI for unpaid and Google One users on 2026-06-18.

  Revisit each one only if its docs show a verified way to run with no tools.

## Why the lock-down matters

These CLIs are agents that can read files, edit files and run commands. Our prompt includes
text the user typed (accessibility limits) and recent task titles. Without the lock-down,
that's a prompt-injection path to running commands on the user's machine. If a CLI can't
run with zero tools, YOUtopia must refuse to use it.

## Verified Claude Code invocation

Sources: the CLI reference and headless docs at code.claude.com (fetched 2026-10-13).

```text
claude -p
  --output-format json
  --system-prompt-file <tmp>/system.txt   # replaces the default prompt entirely
  --tools ""                              # no built-in tools
  --disallowedTools "*"                   # "*" removes every tool, MCP included
  --strict-mcp-config                     # no MCP servers (no --mcp-config given)
  --safe-mode                             # no CLAUDE.md, hooks, plugins, skills, MCP, memory
  --no-session-persistence                # nothing saved, can't be resumed
  --max-turns 1
  --permission-mode dontAsk               # anything that would prompt is denied
  --permission-prompts none               # needs v2.1.259+
  [--model <ai.model>]
stdin  = the user prompt (with the DATA block)
cwd    = a new empty temp dir (deleted afterwards)
```

- **Don't use `--bare`.** Bare mode "never reads OAuth credentials", so it can't use a
  subscription login.
- **Output:** a JSON object with the text in `result`; check `is_error` and `subtype`.
  Failures inside the run (such as missing login) come back as the result on stdout;
  invalid flags go to stderr with a non-zero exit.
- **Auth check:** `claude auth status` prints JSON with `authMethod` (`claude.ai`,
  `api_key`, `none`, …) and exits 1 when not logged in.
- **Version:** older versions reject unknown flags with an error. Map that to "update
  Claude Code (needs v2.1.259 or later)". Record the exact minimum once `--safe-mode`'s
  version is confirmed.

## Steps

1. **Catalog** (`providers/catalog.py`): add `ProviderSpec("claude-code", adapter="cli",
   base_url=None, key_env=None, needs_key=False, default_model=None)`. Extend the `Adapter`
   literal with `"cli"`.
2. **Adapter** (`providers/cli_agent.py`): `ClaudeCodeProvider(model, timeout_s, executable)`
   implementing `complete(system, user, max_tokens)`:
   - Find the binary with `shutil.which("claude")`. Missing → `ProviderError("Install Claude
     Code and run `claude` once to log in.")`.
   - Run the argv list above: no shell, `stdin=user`, `capture_output`, `timeout`, `cwd`
     set to the temp dir, system prompt written to a file in that temp dir.
   - **Environment:** copy `os.environ` but remove every key variable YOUtopia knows
     (`YOUTOPIA_API_KEY`, `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` and the other
     providers' `key_env`), so the subscription login is used and keys don't leak.
     Keep `HOME`/`PATH` so the CLI finds its own login.
   - Parse the JSON from stdout. `is_error`, a non-zero exit, a timeout or invalid JSON →
     `ProviderError`, passed through `redact()` and truncated. Timeouts and 5xx-like
     failures → `RetryableError` (one retry, as with the other adapters).
   - `max_tokens` can't be passed to the CLI. Document that; output size is bounded by our
     validation.
   - `__repr__` shows only name and model.
3. **Registry** (`providers/registry.py`): for the `cli` adapter, skip the URL and key
   checks and build `ClaudeCodeProvider`.
4. **Config:** CLI providers need a longer default timeout. Use
   `max(ai.timeout_s, CLI_MIN_TIMEOUT_S = 60)` for this adapter, or document setting
   `ai.timeout_s 60`. `config set ai.provider claude-code` must validate.
5. **Commands** (`cli.py`):
   - `auth status`: show `claude-code` as "login managed by Claude Code", plus `authMethod`
     from `claude auth status` if the binary exists.
   - `auth set claude-code`: explain there's no key to store; run `claude` to log in.
   - `ai test`: works unchanged through `complete()`.
6. **Generation:** no changes. Validation, the safety filter, the call cap and the template
   fallback already apply to every provider.
7. **Tests** (`tests/test_cli_agent.py`), using a fake `claude` script placed first on
   `PATH` in `tmp_path`. The fake records its argv, cwd, stdin and env to a file, then prints
   canned JSON. Cover:
   - every lock-down flag is present, and `--bare` isn't;
   - no shell; cwd is an empty temp dir that's removed afterwards;
   - stdin carries the prompt; the system prompt file has the right content;
   - the env has none of the key variables;
   - good output; `is_error: true`; non-zero exit with stderr; invalid JSON; timeout (one
     retry); missing binary;
   - `auth status` and `auth set` messages;
   - the end-to-end `today` path with AI tasks coming from the fake CLI.
8. **Docs:**
   - `ai-providers.md`: a "Use your Claude subscription" tab covering setup, that calls
     count against your plan's usage limits, that it's slower, and personal use only.
   - `privacy-and-safety.md`: the lock-down list, and that the provider sees the same
     minimal data.
   - `commands.md`, `roadmap.md` (a new section) and `CLAUDE.md` (layout, rules, security
     bullet: CLI providers run with zero tools in an empty directory).
9. **Checks:** `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`,
   `uv run zensical build --clean`, `uvx pip-audit`.
10. **Manual check on a machine with Claude Code installed** (it isn't on the dev box):
    - `youtopia config set ai.provider claude-code`, then `youtopia ai test`.
    - `youtopia today` produces AI tasks.
    - Confirm the reply has no tool use: run the same flags with `--output-format
      stream-json --verbose` once and check `system/init` lists no tools and no MCP servers.

## Open questions

- The exact minimum Claude Code version for `--safe-mode`.
- Whether managed (organization) settings can still add hooks or MCP servers under
  `--safe-mode`; the docs say managed policy still applies. Document it if so.
- Whether to add a per-provider default timeout to `config.py` instead of the
  `max()` rule.

## Other loose ends from the previous session

- **GitHub Pages** is still set to "Deploy from a branch", so the README sometimes replaces
  the docs site. Switch it to "GitHub Actions"
  (`gh api -X PUT repos/KPoletti/YOUtopia/pages -f build_type=workflow`), then rerun the Docs
  workflow. This needs the owner's go-ahead.
- **M8** work in progress is parked on `claude/m8-security-hardening`: ruff `S` rules,
  literal migration SQL, `0700`/`0600` data files. It has one E501 to fix and its tests
  haven't run yet.
