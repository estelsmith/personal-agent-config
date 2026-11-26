# Junie Global Rules Setup

Compiles modular Markdown rule files under `junie/rules/` into Junie's global instructions file (`~/.junie/AGENTS.md`) and verifies that the installed copy stays in sync.

## What It's For & Why We Use It

- **What it is for**: Maintains your personal, cross-project Junie agent guidelines (such as terminal command conventions in `junie/rules/bash-command-intent.md`) and builds `~/.junie/AGENTS.md` deterministically.
- **Why we use it**:
  - **Modular rules over a monolith**: Keeps unrelated conventions in small, focused Markdown files under `junie/rules/*.md` instead of editing one large `~/.junie/AGENTS.md` by hand.
  - **Drift-free syncing**: Because `hooks/post-install` concatenates rules in sorted filename order and `hooks/doctor` checks the SHA-256 digest and permissions (`0644`), manual edits or broken symlinks in `~/.junie/AGENTS.md` are caught immediately.

## How It Fits Into the Agent Config

- **Always-on behavioral baseline**: `~/.junie/AGENTS.md` applies to every Junie session across repositories, complementing on-demand skills like [`docmancer`](../docmancer/README.md)'s `~/.junie/skills/docmancer/SKILL.md`.
- **Accessible inside [`safehouse`](../safehouse/README.md)**: `junie-safehouse` mounts `~/.junie` read/write into the sandbox so Junie can read `AGENTS.md`, skills, and session state normally.

## How It Works

`junie/manifest` currently holds comments only—static `~/.junie/` files can be added there later, while `~/.junie/AGENTS.md` is generated dynamically by hooks:

1. `junie/hooks/_junie.py` discovers all non-empty `*.md` files in `junie/rules/` sorted by filename, normalizes line endings, and joins them with blank lines (`\n\n`).
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
| `junie/rules/*.md` | Source rules | Modular Markdown rule files concatenated in sorted filename order (currently `bash-command-intent.md`). |
| `junie/manifest` | Optional static files | Placeholder for any static `~/.junie/` files to sync directly. |
| `junie/hooks/post-install` | Build & sync hook | Renders `junie/rules/*.md` into `~/.junie/AGENTS.md` (`0644`). |
| `junie/hooks/doctor` | Health check hook | Verifies `~/.junie/AGENTS.md` exists as a regular file with matching SHA-256 and `0644` mode. |
| `junie/hooks/_junie.py` | Shared helper module | Rule discovery, deterministic rendering, atomic writes, and SHA-256/mode checks. |
