# AGENTS.md

Repository-specific guidance for agents working in `personal-agent-config` (a macOS-only personal agent setup; see `README.md` for architecture, manifest syntax, and CLI flags).

## Repository Boundaries

- **Global rules vs. repo instructions:** `junie/rules/*.md` compiles into `~/.junie/AGENTS.md` and applies to *all* repositories. Put rules meant for every repo in `junie/rules/`, and keep rules specific to developing this repository in this `AGENTS.md`.
- **Edit repo sources, not deployed files:** Never directly edit deployed targets under `~/` (such as `~/.junie/AGENTS.md`, `~/litellm-proxy/*`, `~/bin/junie-safehouse`, or `~/.bash_profile`). Edit the source files in this repo and sync via `bin/install` only when appropriate.
- **Treat `wishlist.md` as backlog:** Items in `wishlist.md` describe future ideas and known debt (such as hardcoded paths in `safehouse/acp.json` or replacing the system-Python assumption), not implemented behavior.
- **Secrets:** Never commit `litellm-proxy/.env` or real API keys/tokens. Use `.env.example` and `sync-or-seed` manifest entries instead.

## Safe Testing & Verification

Live `bin/install` and `bin/doctor` runs touch real `$HOME` files, rewrite `~/.bash_profile`, download `~/bin/mise`, and run `docker compose` (`pull`/`build`/`down`/`up`) in `~/litellm-proxy`.

- **Primary validation:** Run the isolated test suite, which uses temporary `HOME` directories and fake `docker`/`mise` shims:
  ```bash
  python3 -m unittest discover -s tests
  ```
- **Safe preview:** Use `bin/install --dry-run [system]` before running any live install.
- **Keep tests updated:** When changing `bin/`, manifest entries, or `*/hooks/*`, add or update corresponding coverage in `tests/test_cli.py`.
- **Live runs:** Only run `bin/install` or `bin/doctor` against the real `$HOME` when intentionally verifying or deploying changes to the host environment, and check `git status` / `git diff` afterward to ensure no untracked secrets or artifacts remain.

## Implementation Conventions

- **Stdlib-only Python (`#!/usr/bin/env python3`):** `bin/install`, `bin/doctor`, `bin/_lib.py`, and `*/hooks/*` must use only the Python standard library. Even though `#!/usr/bin/env python3` resolves to Mise's Python 3.15 in an activated shell, these scripts must also run under `/usr/bin/python3` on unbootstrapped macOS machines (which is why `mise/hooks/_mise.py` includes a fallback TOML parser when `tomllib` is unavailable).
- **Manifest invariants (`bin/_lib.py`):** Source paths must stay within `<system>/`, target paths must resolve to absolute paths (after `~`/env expansion), and `sync-or-seed` requires `<primary>|<seed>`.
- **Hook contract:** Hook scripts (`hooks/pre-install`, `hooks/post-install`, `hooks/doctor`) must be executable (`0755`), run with `cwd` set to `<system>/`, and emit failures prefixed with `[FAIL] ` so `extract_hook_failures` surfaces them in the `Failed Checks:` summary.
- **File writes & line endings:** Preserve LF line endings (`.gitattributes`) and use atomic temp-file writes (`atomic_write_bytes` / `tempfile` + `os.replace`) when updating target files.

## Cross-System Coupling & Ordering

`discover_systems()` orders systems **alphabetically** (`docmancer`, `junie`, `litellm-proxy`, `mise`, `safehouse`), which does not match runtime dependency order:

- **`mise` ↔ `docmancer`:** `docmancer` depends on the Mise-managed toolchain (`~/bin/mise`). Changes to `mise/tools.toml` (such as `embeddings-openai` / `pysocks` extras) or `docmancer/mise-env.toml` must stay aligned with `docmancer/hooks/doctor`. On a fresh host, `mise` must be installed before `docmancer`.
- **`litellm-proxy` ↔ `safehouse`:** `litellm-proxy/hooks/post-install` syncs `LITELLM_MASTER_KEY` from `~/litellm-proxy/.env` into `~/.bash_profile`, and `safehouse/junie-safehouse` forwards it via `--env-pass`. `litellm-proxy/hooks/post-install` only rebuilds/restarts Docker Compose when `FILES_CHANGED=1` (or the stack is unhealthy).
- **`junie` rules compilation:** `junie/hooks/post-install` (not `junie/manifest`) concatenates `junie/rules/*.md` alphabetically into `~/.junie/AGENTS.md` and fails if any rule file is empty (`junie/hooks/_junie.py`).
