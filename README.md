<img src="assets/banner.svg" alt="Personal Agent Config" width="100%">

# Estel's Personal AI Agent

This is my personal configuration repository for standing up and maintaining a local AI coding agent environment on **macOS** around **JetBrains** IDEs and **Junie**.

I built it so I can bootstrap my entire agent setup from scratch on a fresh machine (declarative configs, global agent rules, local model routing, documentation search, and sandboxing) and verify that everything stays in sync over time. It's tailored specifically to my workflow, though if you run a similar macOS + JetBrains + Junie stack, feel free to take ideas from it for your own setup.

## Systems

Each top-level directory is an independent **system** handling one part of the stack. See each system's README for setup details, prerequisites, and internals:

| System | What It Is For | Why I Use It | Docs |
| --- | --- | --- | --- |
| `mise` | Runtime and CLI tool version management. | Keeps runtimes and agent tools pinned and reproducible across interactive shells, IDE subshells, and sandboxed runs without relying on system packages. | [mise/README.md](mise/README.md) |
| `docmancer` | Local documentation indexing and search. | Lets the agent query curated, up-to-date library docs locally instead of relying on stale training data. | [docmancer/README.md](docmancer/README.md) |
| `junie` | Global agent rules compiled into Junie's `AGENTS.md`. | Keeps my coding-agent conventions organized in small, version-controlled files and synced consistently across projects. | [junie/README.md](junie/README.md) |
| `litellm-proxy` | Local LLM gateway with model routing and request logging. | Provides a single local endpoint, routes turns by complexity to balance cost and quality, and keeps provider API keys out of the agent process. | [litellm-proxy/README.md](litellm-proxy/README.md) |
| `safehouse` | Sandboxing wrapper for Junie CLI and JetBrains IDE sessions. | Restricts the agent to the active project and explicit tool directories instead of giving it unrestricted access to the rest of the machine. | [safehouse/README.md](safehouse/README.md) |

## How It Works

The repository uses a lightweight Python CLI (`bin/install` and `bin/doctor`) built around two conventions: **manifests** for declarative file placement and **hooks** for system-specific setup and verification:

```text
<system>/
├── manifest             # Optional: maps repo files -> target paths with permissions & mode
├── hooks/
│   ├── pre-install      # Optional: runs before manifest files are synced
│   ├── post-install     # Optional: runs after manifest files are synced
│   └── doctor           # Optional: custom health/runtime checks run by bin/doctor
└── ...                  # System-specific configs, rules, skills, or services
```

1. **System auto-discovery**: Both `bin/install` and `bin/doctor` automatically discover any top-level directory containing a `manifest` file or a `hooks/` directory (ignoring dotfiles, `bin/`, `tests/`, and `__pycache__/`).
2. **Manifest syncing**: Each line in `<system>/manifest` follows:
   ```text
   <mode> <source> <target> [sync|seed|sync-or-seed]
   ```
   - `sync` (default): Atomically writes the file if missing, if its SHA-256 hash differs from the repo, if its permissions differ, or if the target is a symlink.
   - `seed`: Copies `<source>` to `<target>` only when the target does not exist yet, preserving local edits and secrets afterward.
   - `sync-or-seed` (`<primary>|<seed>`): Syncs `<primary>` when it exists in the repo (for example, a gitignored `.env`), or falls back to `seed` using `<seed>` (for example, `.env.example`).
3. **Lifecycle hooks**: Before and after syncing files, `bin/install` runs executable scripts in `<system>/hooks/` for system-specific setup (such as installing runtimes, compiling generated configs, or managing background services). `bin/doctor` runs `<system>/hooks/doctor` after verifying manifest file hashes and permissions.

## Quick Start

1. **Preview what will be installed** without touching your home directory or running hooks:
   ```bash
   bin/install --dry-run
   ```
2. **Install all systems** (or target specific ones, e.g., `bin/install junie`):
   ```bash
   bin/install
   ```
   > **Note:** Check individual system READMEs for machine prerequisites, install order dependencies, or first-time steps (such as filling in API keys when a system seeds a local config with placeholders).
3. **Verify your setup**:
   ```bash
   bin/doctor
   ```

## CLI Reference

### `bin/install [OPTIONS] [SYSTEM ...]`

Installs or updates manifest files and runs `pre-install` / `post-install` hooks across all discovered systems (or only the named `SYSTEM`s).

- `-n`, `--dry-run`: Preview planned file installs/updates/seeds and hook executions without modifying disk or running hooks.
- `--no-hooks`: Sync manifest files only, skipping `pre-install` and `post-install` hooks.
- `-f`, `--force`: Reinstall `sync` files even when SHA-256 and permissions already match (also sets `FILES_CHANGED=1` for `post-install` hooks).
- `--list`: List all discovered system names and exit.

Prints a color-coded per-system status summary (`green` when unchanged, `yellow` when files were installed/updated/seeded, `red` on failure) and a `Failed Checks:` breakdown if anything fails.

### `bin/doctor [OPTIONS] [SYSTEM ...]`

Verifies installed state and runtime health across all discovered systems (or only the named `SYSTEM`s):

- Confirms every `sync` entry exists, matches the repository SHA-256 digest, and has the exact file mode (and flags symlinks or directory conflicts).
- Confirms every `seed` entry exists and warns if its permissions are looser than the manifest mode.
- Runs `<system>/hooks/doctor` (if present) for live system checks.
- `--list`: List all discovered system names and exit.

## Adding a New System

Any top-level directory `<system>/` with a `manifest` file or a `hooks/` directory is automatically picked up by `bin/install` and `bin/doctor`:

1. Create `<system>/manifest` with one mapping per line (`~` and environment variables are expanded in `<target>`):
   ```text
   # <mode> <source> <target> [sync|seed|sync-or-seed]
   0644 my-config.json    ~/.config/my-agent/config.json
   0600 .env|.env.example ~/.config/my-agent/.env        sync-or-seed
   ```
2. Optionally add executable hook scripts under `<system>/hooks/`:
   - `hooks/pre-install`: Runs before manifest sync (`REPO_ROOT`, `SYSTEM_NAME`, `SYSTEM_DIR`).
   - `hooks/post-install`: Runs after manifest sync (`REPO_ROOT`, `SYSTEM_NAME`, `SYSTEM_DIR`, `FILES_INSTALLED`, `FILES_UPDATED`, `FILES_SEEDED`, `FILES_UNCHANGED`, `FILES_CHANGED`).
   - `hooks/doctor`: Runs after manifest verification (`REPO_ROOT`, `SYSTEM_NAME`, `SYSTEM_DIR`). Lines prefixed with `[FAIL]` are surfaced in the bottom `Failed Checks:` summary.

## Tests

Run the CLI test suite (uses isolated temporary directories so it won't touch your actual home directory):

```bash
python3 -m unittest discover -s tests
```
