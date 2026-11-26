# Docmancer Setup

Configures [Docmancer](https://docmancer.dev/) for local documentation indexing and semantic/RAG lookup backed by SQLite, `sqlite-vec`, and local [Ollama](https://ollama.com/) embeddings, and installs a Junie Agent Skill for consulting indexed docs before writing code.

## What It's For & Why We Use It

- **What it is for**: Indexes external library/framework documentation locally and exposes token-budgeted search and page/section expansion strictly via `docmancer docs` (`docs query`, `docs add`, `docs list`, `docs sync`, `docs remove`)—without using Docmancer's Shared Memory surface (`docmancer ask`).
- **Why we use it**:
  - **Accuracy over stale weights**: Coding agents look up current APIs, configuration schemas, and conventions from indexed docs instead of guessing from outdated training data.
  - **Local & private embeddings**: Runs entirely locally with SQLite + `sqlite-vec` and Ollama (`embeddinggemma-2:740m`), avoiding per-query embedding fees or external vector database setup.
  - **Budget-controlled context**: Returns compact, relevant sections rather than flooding the agent context window with raw web pages.

## How It Fits Into the Agent Config

- **Depends on [`mise`](../mise/README.md)**: `mise` installs `pipx:docmancer` (with `embeddings-openai` and `pysocks`), and `docmancer/mise-env.toml` places `OPENAI_BASE_URL` and `OPENAI_API_KEY` into Mise's `conf.d` so `mise exec -- docmancer` works identically from terminals, IDEs, and sandboxes.
- **Extends [`junie`](../junie/README.md)**: Installs `~/.junie/skills/docmancer/SKILL.md` so Junie automatically knows when and how to search or index docs before coding against external libraries.
- **Compatible with [`safehouse`](../safehouse/README.md)**: `safehouse/junie-local.sb` grants sandboxed Junie sessions read/write access to `~/.docmancer`, letting agents query and refresh the index safely from inside the sandbox.

## How It Works

```text
Junie / User ──► mise exec -- docmancer ...
                     │
                     ├── ~/.config/mise/conf.d/docmancer.toml
                     │     (injects OPENAI_BASE_URL=http://localhost:11434/v1, OPENAI_API_KEY=ollama)
                     │
                     ├── ~/.docmancer/docmancer.yaml
                     │     (sqlite + sqlite-vec + embeddinggemma-2:740m @ 768 dims)
                     │
                     └── Ollama (localhost:11434) ──► ~/.docmancer/docmancer.db & extracted/
```

Three pieces work together:

1. **Docmancer configuration (`docmancer.yaml` → `~/.docmancer/docmancer.yaml`)**:
   - **Index**: `sqlite` storing metadata in `./docmancer.db` and extracted pages in `./extracted` (resolved relative to `~/.docmancer/`, not the current working directory; `docmancer docs ...` automatically falls back to `~/.docmancer/docmancer.yaml` from any directory without a local `./docmancer.yaml`, or pass `--config ~/.docmancer/docmancer.yaml` to force the global index).
   - **Vector store**: `sqlite-vec` for local vector search without an external vector database.
   - **Embeddings**: `openai`-compatible provider pointing to `embeddinggemma-2:740m` (`dimensions: 768`).
   - **Retrieval**: `local` profile (hybrid FTS5 + `sqlite-vec` dense retrieval by default).
2. **Mise environment injection (`mise-env.toml` → `~/.config/mise/conf.d/docmancer.toml`)**:
   - Sets `OPENAI_BASE_URL = "http://localhost:11434/v1"` and `OPENAI_API_KEY = "ollama"` inside Mise's `conf.d`.
   - Running `mise exec -- docmancer ...` always picks up the Mise-managed `pipx:docmancer` binary (installed with `embeddings-openai` and `pysocks`) and these environment variables—even in non-interactive shells or IDE subshells where `~/.bash_profile` was not sourced.
3. **Junie Agent Skill (`skills/docmancer/SKILL.md` → `~/.junie/skills/docmancer/SKILL.md`)**:
   - Guides Junie through documentation-only lookup (`docs list`, `docs query` with `--budget`, `--format`, `--expand` / `--expand page`, and `docs add` / `docs sync` / `docs remove`), warns against `docmancer ask` (Shared Memory), and enforces invoking `mise exec -- docmancer` rather than a bare system binary.

## Prerequisites

1. **Install the `mise` system first** (provides `~/bin/mise` and `pipx:docmancer[embeddings-openai,with=pysocks]`):
   ```bash
   bin/install mise
   ```
2. **Ollama running locally** with the configured embedding model pulled:
   ```bash
   ollama pull embeddinggemma-2:740m
   ```
3. *(If running Junie inside Agent Safehouse)*: [`safehouse/junie-local.sb`](../safehouse/junie-local.sb) grants read/write access to `~/.docmancer` so sandboxed agents can read and update the local index.

## Quick Start

```bash
# Sync Docmancer config, Mise conf.d env, and the Junie skill
bin/install docmancer

# Verify Mise env vars, `mise exec -- docmancer --version`, `openai`, and `socks` imports
bin/doctor docmancer
```

## Common Commands

Always run Docmancer through `mise exec -- docmancer`, and use `docmancer docs ...` strictly for documentation lookup (not `docmancer ask`, which searches Shared Memory):

```bash
# List currently indexed documentation sources (add --all for individual pages/files)
mise exec -- docmancer docs list
mise exec -- docmancer docs list --all

# Index a documentation website, GitHub repo, or local docs directory
mise exec -- docmancer docs add https://example.com/docs
mise exec -- docmancer docs add https://github.com/owner/repo
mise exec -- docmancer docs add /path/to/docs

# Search indexed docs within a token budget (include the tool/library name in the query)
mise exec -- docmancer docs query "example routing configuration" --budget 2400

# Expand adjacent sections or full page context for top matches
mise exec -- docmancer docs query "example routing configuration" --limit 2 --budget 3000 --expand
mise exec -- docmancer docs query "example routing configuration" --limit 1 --budget 4000 --expand page

# Return structured JSON output
mise exec -- docmancer docs query "example routing configuration" --format json

# Refresh all existing sources or a single source
mise exec -- docmancer docs sync
mise exec -- docmancer docs sync https://example.com/docs

# Remove an indexed source
mise exec -- docmancer docs remove https://example.com/docs
```

## Files & Manifest

| Repo Source | Target Path | Mode | Purpose |
| --- | --- | --- | --- |
| `docmancer/docmancer.yaml` | `~/.docmancer/docmancer.yaml` | `0644` | SQLite, `sqlite-vec`, Ollama embedding model, and retrieval settings. |
| `docmancer/mise-env.toml` | `~/.config/mise/conf.d/docmancer.toml` | `0644` | Injects `OPENAI_BASE_URL` and `OPENAI_API_KEY` into Mise environments. |
| `docmancer/skills/docmancer/SKILL.md` | `~/.junie/skills/docmancer/SKILL.md` | `0644` | Junie skill instructions for consulting and indexing docs. |
| `docmancer/hooks/doctor` | *(hook)* | `0755` | Health check script run by `bin/doctor docmancer`. |

## Health Checks (`bin/doctor docmancer`)

After checking manifest file hashes and modes, `docmancer/hooks/doctor` verifies:

1. `~/bin/mise` exists and is executable.
2. `~/bin/mise env --json` defines non-empty `OPENAI_BASE_URL` and `OPENAI_API_KEY`.
3. `~/bin/mise exec -- docmancer --version` succeeds.
4. Docmancer's Python interpreter (`mise which docmancer` shebang) can `import openai` (from the `embeddings-openai` extra) and `import socks` (from `pysocks`, required when SOCKS proxies are configured in the environment).
