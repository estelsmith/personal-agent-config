<img src="assets/banner.svg" alt="Personal Agent Config" width="100%">

# Estel's Personal AI Agent

This is my personal setup for standing up and maintaining a local AI coding agent environment on **macOS** around **JetBrains** IDEs and **Junie**.

I built it so I can bootstrap a fresh machine (declarative configs, global agent rules, local model routing, doc search, and sandboxing) and verify everything stays in sync instead of drifting into half-remembered dotfiles. It's macOS-only and tailored specifically to my JetBrains + Junie workflow, not a generic cross-platform dotfile manager. Though if you run a similar stack, feel free to borrow pieces for your own setup.

## Systems

Each top-level directory is an independent **system** handling one part of the stack. See each system's README for prerequisites, commands, and internals:

| System | What It Is For | Why I Use It | Docs |
| --- | --- | --- | --- |
| `mise` | Runtime and CLI tool version management. | Keeps runtimes and agent tools pinned so interactive shells, IDE subshells, and sandboxed runs all see the same versions instead of whatever macOS shipped. | [mise/README.md](mise/README.md) |
| `docmancer` | Local documentation indexing and search. | Lets the agent query curated, up-to-date library docs locally rather than guessing from stale training data. | [docmancer/README.md](docmancer/README.md) |
| `junie` | Global agent rules compiled into Junie's `AGENTS.md` and reusable skills. | Rather than editing one large `~/.junie/AGENTS.md` by hand, I keep rules in small, focused files under `junie/rules/` and stitch them together on install. | [junie/README.md](junie/README.md) |
| `litellm-proxy` | Local LLM gateway with model routing and request logging. | Gives me one local endpoint, routes turns by complexity so simple tasks don't burn expensive tokens, and keeps provider API keys out of the agent process. | [litellm-proxy/README.md](litellm-proxy/README.md) |
| `safehouse` | Sandboxing wrapper for Junie CLI and JetBrains IDE sessions. | Restricts the agent to the active project and explicit tool directories instead of giving it free rein over my home directory. | [safehouse/README.md](safehouse/README.md) |

## How It Works

The repo is driven by a small Python CLI (`bin/install` and `bin/doctor`) built on Python's standard library alone. Since `/usr/bin/python3` already ships on macOS, I don't need to bootstrap a third-party dotfile tool before I can even install `mise`. Simple is better.

Every system follows the same layout:

```text
<system>/
├── manifest             # Optional: maps repo files -> target paths with permissions & mode
├── hooks/
│   ├── pre-install      # Optional: runs before manifest files are synced
│   ├── post-install     # Optional: runs after manifest files are synced
│   └── doctor           # Optional: custom health/runtime checks run by bin/doctor
└── ...                  # System-specific configs, rules, skills, or services
```

- **System auto-discovery:** `bin/install` and `bin/doctor` pick up any top-level directory containing a `manifest` file or a `hooks/` folder (ignoring dotfiles, `bin/`, `tests/`, and `__pycache__/`). They process systems alphabetically rather than resolving a dependency graph, which mostly doesn't matter except on a brand-new machine where `mise` has to exist before `docmancer`.
- **Manifest syncing:** Each line in `<system>/manifest` uses `<mode> <source> <target> [sync|seed|sync-or-seed]`:
  - **sync:** (default) Atomically writes the file if it's missing, its SHA-256 hash differs from the repo, its permissions differ, or the target is a symlink.
  - **seed:** Copies `<source>` to `<target>` only when the target doesn't exist yet, preserving local edits and secrets afterward.
  - **sync-or-seed:** (`<primary>|<seed>`) Syncs `<primary>` when it exists in the repo (for example, a gitignored `.env`), or falls back to seeding `<seed>` (like `.env.example`).
- **Lifecycle hooks:** `bin/install` runs executable scripts in `<system>/hooks/` before and after syncing files (for tasks like installing runtimes, compiling generated configs, or restarting services). `bin/doctor` runs `<system>/hooks/doctor` after checking manifest hashes and permissions.

## Quick Start

```bash
# Preview planned file installs and hooks without touching ~/
bin/install --dry-run

# On a fresh machine, install mise first since docmancer relies on its toolchain
bin/install mise

# Install everything (or target specific systems, like `bin/install junie`)
bin/install

# Verify installed files, permissions, and live runtime health
bin/doctor
```

Check each system's README for machine prerequisites or first-time manual steps (like filling in API keys when a system seeds a placeholder `.env`).

## CLI Reference

### `bin/install [OPTIONS] [SYSTEM ...]`

Installs or updates manifest files and runs `pre-install` / `post-install` hooks across all discovered systems (or only the `SYSTEM` names you pass). Prints a color-coded summary (`green` when unchanged, `yellow` when files changed, `red` on failure) plus a `Failed Checks:` section if anything broke.

- **`-n`, `--dry-run`:** Preview planned installs, updates, seeds, and hooks without modifying disk or running hooks.
- **`--no-hooks`:** Sync manifest files only, skipping `pre-install` and `post-install` hooks.
- **`-f`, `--force`:** Reinstall `sync` files even when SHA-256 and permissions already match (also sets `FILES_CHANGED=1` for `post-install` hooks).
- **`--list`:** List discovered system names and exit.

### `bin/doctor [OPTIONS] [SYSTEM ...]`

Verifies installed state and runtime health across all discovered systems (or only the `SYSTEM` names you pass).

- **Sync verification:** Confirms every `sync` entry exists, matches the repo SHA-256 digest, and has the exact file mode (flagging symlinks or directory conflicts).
- **Seed verification:** Confirms every `seed` entry exists and warns if its permissions are looser than the manifest mode.
- **Live checks:** Runs `<system>/hooks/doctor` (if present).
- **`--list`:** List discovered system names and exit.

## Adding a New System

Create a top-level `<system>/` directory with a `manifest` file, a `hooks/` folder, or both, and `bin/install` and `bin/doctor` will pick it up automatically:

1. Add `<system>/manifest` with one mapping per line (`~` and environment variables expand in `<target>`):
   ```text
   # <mode> <source> <target> [sync|seed|sync-or-seed]
   0644 my-config.json    ~/.config/my-agent/config.json
   0600 .env|.env.example ~/.config/my-agent/.env        sync-or-seed
   ```
2. Optionally add executable (`0755`) hook scripts under `<system>/hooks/`:
   - **`hooks/pre-install`:** Runs before manifest sync (`REPO_ROOT`, `SYSTEM_NAME`, `SYSTEM_DIR`).
   - **`hooks/post-install`:** Runs after manifest sync (`REPO_ROOT`, `SYSTEM_NAME`, `SYSTEM_DIR`, `FILES_INSTALLED`, `FILES_UPDATED`, `FILES_SEEDED`, `FILES_UNCHANGED`, `FILES_CHANGED`).
   - **`hooks/doctor`:** Runs after manifest checks (`REPO_ROOT`, `SYSTEM_NAME`, `SYSTEM_DIR`). Lines prefixed with `[FAIL] ` show up in the `Failed Checks:` summary.

## Tests

```bash
# Run the CLI test suite in temporary HOME directories (won't touch your real ~/)
python3 -m unittest discover -s tests
```
