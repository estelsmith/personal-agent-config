# Junie Global Rules

This system compiles my modular Markdown rule files under `junie/rules/` into Junie's global instructions file (`~/.junie/AGENTS.md`) and makes sure the installed copy stays in sync.

## Why I Use It

Rather than editing one large `~/.junie/AGENTS.md` file by hand, I keep unrelated conventions in small, focused files under `junie/rules/` (such as terminal command intent, preferring Docmancer over guessing APIs, and avoiding emdashes). Those rules apply across every Junie session and repository.

Because `hooks/post-install` renders `~/.junie/AGENTS.md` deterministically in sorted filename order and `hooks/doctor` verifies its SHA-256 digest and permissions (`0644`), accidental manual edits or stray symlinks get caught right away.

## How It Fits In

`~/.junie/AGENTS.md` sets my always-on behavioral baseline across projects, complementing on-demand skills like [`docmancer`](../docmancer/README.md)'s `~/.junie/skills/docmancer/SKILL.md`. Inside [`safehouse`](../safehouse/README.md), `junie-safehouse` mounts `~/.junie` read/write so Junie can read `AGENTS.md`, skills, and session state normally.

## How It Works

`junie/manifest` currently holds comments only. Static `~/.junie/` files can be added there later, while `~/.junie/AGENTS.md` is generated dynamically by hooks:

1. `junie/hooks/_junie.py` collects every non-empty `*.md` file in `junie/rules/` sorted by filename, normalizes line endings, and joins them with blank lines (`\n\n`).
2. `junie/hooks/post-install` atomically writes the rendered output to `~/.junie/AGENTS.md` (`0644`) whenever the file is missing, is a symlink, or differs in SHA-256 hash or mode.
3. `junie/hooks/doctor` re-renders `junie/rules/*.md` in memory and verifies that `~/.junie/AGENTS.md` is a regular file with the exact expected SHA-256 digest and `0644` permissions.

## Quick Start

```bash
# Render junie/rules/*.md and sync ~/.junie/AGENTS.md
bin/install junie

# Verify ~/.junie/AGENTS.md matches junie/rules/*.md
bin/doctor junie
```

## Files & Hooks

| Path | Role | Details |
| --- | --- | --- |
| `junie/rules/*.md` | Source rules | Modular Markdown rule files concatenated in sorted filename order (e.g., `bash-command-intent.md`, `docmancer-first.md`). |
| `junie/manifest` | Optional static files | Placeholder for any static `~/.junie/` files to sync directly. |
| `junie/hooks/post-install` | Build and sync hook | Renders `junie/rules/*.md` into `~/.junie/AGENTS.md` (`0644`). |
| `junie/hooks/doctor` | Health check hook | Verifies `~/.junie/AGENTS.md` exists as a regular file with matching SHA-256 and `0644` mode. |
| `junie/hooks/_junie.py` | Shared helper module | Rule discovery, deterministic rendering, atomic writes, and SHA-256/mode checks. |
