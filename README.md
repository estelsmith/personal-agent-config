# Personal Agent Config

Central repository for managing local AI agent tooling configurations (`litellm-proxy`, `safehouse`, and future systems) with a shared CLI for verifying and installing files.

## Commands

### `bin/doctor [SYSTEM ...]`

Checks configuration sync and health across all discovered systems (or only the specified system names):

- Verifies every `sync` file in each system's `manifest` exists, matches the repository file's SHA-256 hash, and has the expected file mode.
- Verifies every `seed` file (such as `~/litellm-proxy/.env`) exists and checks its permissions without requiring a hash match.
- Runs `<system>/hooks/doctor` (if present) for system-specific health checks (e.g., `litellm-proxy` Docker Compose stack state/health, `.env` keys, and `~/.bash_profile` `LITELLM_MASTER_KEY` sync; `safehouse` executable/binary prerequisites and ACP config).

### `bin/install [OPTIONS] [SYSTEM ...]`

Installs missing or mismatched files and runs system lifecycle hooks:

- Installs missing `sync` files and atomically updates files whose SHA-256 hash or permissions differ.
- Seeds missing `seed` files (such as `.env.example` -> `~/litellm-proxy/.env`) while preserving existing local files; `sync-or-seed` (`<primary>|<seed>`) syncs the primary file (such as a gitignored `.env`) when present in the repo and falls back to seeding from `<seed>` when absent.
- Runs `<system>/hooks/pre-install` (before file sync) and `<system>/hooks/post-install` (after file sync, e.g., `litellm-proxy` syncing `LITELLM_MASTER_KEY` into `~/.bash_profile` and pulling/building/restarting the Docker Compose stack when files changed, or checking stack health and only starting it if stopped or unhealthy when unchanged).
- Prints a per-system summary report.

Useful flags:

- `--dry-run` / `-n`: Preview file changes and hooks without modifying files or running hooks.
- `--no-hooks`: Install/sync files only, skipping lifecycle hooks.
- `--force` / `-f`: Reinstall `sync` files even when SHA-256 and permissions match.
- `--list`: List discovered systems.

## Adding a New System

Any top-level directory `<system>/` containing a `manifest` file or a `hooks/` directory is automatically discovered by `bin/doctor` and `bin/install`.

1. Add `<system>/manifest` with one mapping per line:

   ```text
   # <mode> <source> <target> [sync|seed|sync-or-seed]
   0644 my-config.json    ~/.config/my-agent/config.json
   0600 .env|.env.example ~/.config/my-agent/.env        sync-or-seed
   ```

2. Optionally add executable hook scripts under `<system>/hooks/`:
   - `hooks/doctor`: Custom health/runtime checks run by `bin/doctor`.
   - `hooks/pre-install`: Executed before `bin/install` syncs files.
   - `hooks/post-install`: Executed after `bin/install` syncs files (receives `REPO_ROOT`, `SYSTEM_NAME`, `SYSTEM_DIR`, `FILES_INSTALLED`, `FILES_UPDATED`, `FILES_SEEDED`, `FILES_UNCHANGED`, and `FILES_CHANGED`).
