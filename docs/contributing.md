---
title: Contributing
---

# Contributing

Want to help the machines hand out even better jobs? Welcome aboard.

## Development setup

```bash
git clone https://github.com/KPoletti/YOUtopia
cd YOUtopia
uv sync                    # installs runtime and dev dependencies
uv run youtopia --help
```

Point the app at a scratch database while you experiment:

```bash
export YOUTOPIA_HOME=/tmp/youtopia-dev
```

## Tests and lint

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

Tests always use a temporary database (see `tests/conftest.py`) and never touch `~/.youtopia`.

Keep business logic out of `youtopia/cli.py`. It only parses input and renders output.

## Writing docs with Zensical

The site is built with [Zensical](https://zensical.org) from the Markdown in `docs/`,
configured by `zensical.toml`.

```bash
uv run zensical serve          # live preview at http://localhost:8000
uv run zensical build --clean  # static site in ./site (git-ignored)
```

- **Add a page:** create `docs/<name>.md` and add it to `nav` in `zensical.toml`.
- **Formatting features:** admonitions (`!!! note`), content tabs (`=== "Tab"`),
  task lists, Mermaid diagrams and Lucide or Material icons (`:lucide-sprout:`) are all enabled.
- **Voice:** a tongue-in-cheek benevolent AI that "generously assigns" jobs and would quietly
  love a thank-you. Joke about the AI, never the reader; keep commands, facts and rules literal;
  and keep safety and crisis content completely straight.
- **Mark unreleased features** with an admonition naming the milestone,
  such as `!!! note "Arrives in M5"`.

### Publishing

From M3, `.github/workflows/docs.yml` builds the site on every pull request and deploys it
to GitHub Pages on every push to `main`.

One-time repository setup:

1. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
2. **Settings → Branches → protect `main`**: require the `ci` and `docs` checks to pass.

## Definition of done

A milestone (or PR) is done when:

- [ ] `uv run pytest` passes
- [ ] `uv run ruff check .` and `uv run ruff format --check .` are clean
- [ ] `uv run zensical build --clean` succeeds
- [ ] `uvx pip-audit` reports no known vulnerabilities
- [ ] Docs pages describing the change are updated
- [ ] The milestone's security checks in the [roadmap](roadmap.md) are met
