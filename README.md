# Personal Agent Config

A declarative, idempotent configuration repository for managing a local AI coding agent environment on macOS. It pairs versioned configs, rules, and wrappers with a lightweight Python CLI (`bin/install` and `bin/doctor`) that syncs files to your home directory, handles secrets safely, runs lifecycle hooks, and verifies runtime health.

## Systems & Why We Use Them

Each top-level directory is an independent **system** solving one part of a reliable, cost-aware, and sandboxed coding-agent workflow around JetBrains Junie:

| System | What It Is For | Why We Use It | Docs |
| --- | --- | --- | --- |
| `mise` | Global runtime and CLI tool version management (`python`, `uv`, `docmancer`). | Keeps agent dependencies pinned and reproducible across interactive shells, IDE subshells, and sandboxed runs without relying on system packages. | [mise/README.md](mise/README.md) |
| `docmancer` | Local documentation indexing, RAG search, and a Junie lookup skill. | Lets agents query curated, up-to-date library docs locally instead of guessing from stale training data or paying for external embeddings. | [docmancer/README.md](docmancer/README.md) |
| `junie` | Modular global agent rules compiled into `~/.junie/AGENTS.md`. | Keeps personal coding-agent conventions version-controlled in small files and synced consistently across all projects. | [junie/README.md](junie/README.md) |
| `litellm-proxy` | Local LLM gateway with complexity-based routing, logging, and Junie adapters. | Gives agents a single local endpoint, routes simple vs. complex turns to appropriate models to balance cost and quality, and keeps upstream provider keys out of the agent process. | [litellm-proxy/README.md](litellm-proxy/README.md) |
| `safehouse` | Least-privilege sandboxing wrapper for Junie CLI and JetBrains IDE sessions. | Limits autonomous agents to the active project and explicit tool directories instead of giving them unrestricted access to the rest of the machine. | [safehouse/README.md](safehouse/README.md) |

## How It Works

The repository is built around two conventions—**manifests** for declarative file placement and **hooks** for imperative setup and verification:

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

## Quick Start (First-Time Setup)

1. **Preview what will be installed** without touching your home directory or running hooks:
   ```bash
   bin/install --dry-run
   ```
2. **Install all systems** (or target specific ones, e.g. `bin/install mise docmancer`):
   ```bash
   bin/install
   ```
   > **Note:** Install `mise` before (or alongside) `docmancer`, since `docmancer` depends on the Mise-managed toolchain.
3. **Populate secrets if prompted**: On a fresh machine without a gitignored `litellm-proxy/.env`, `bin/install` seeds `~/litellm-proxy/.env` from `litellm-proxy/.env.example` with placeholder keys. Follow [litellm-proxy/README.md](litellm-proxy/README.md) to fill in your API keys and recreate the proxy containers.
4. **Verify your setup**:
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

Run the CLI integration test suite (uses isolated temporary `HOME` directories and fake `docker`/`mise` shims):

```bash
python3 -m unittest discover -s tests
```
