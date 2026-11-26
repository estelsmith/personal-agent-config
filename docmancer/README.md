# Docmancer

This system configures [Docmancer](https://docmancer.dev/) for local documentation indexing and search backed by SQLite, `sqlite-vec`, and local [Ollama](https://ollama.com/) embeddings, and installs a Junie skill so the agent checks indexed docs before writing code.

## Why I Use It

Coding agents often guess at APIs, config schemas, and CLI flags from stale training data. Indexing official documentation locally lets Junie search current references inside a controlled token budget instead of guessing or pulling entire raw web pages into context.

Everything runs locally with SQLite, `sqlite-vec`, and Ollama (`embeddinggemma-2:740m`), avoiding per-query embedding fees or an external vector database. Queries stick strictly to `docmancer docs` (`docs query`, `docs add`, `docs list`, `docs sync`, `docs remove`), leaving Docmancer's Shared Memory (`docmancer ask`) unused.

## How It Fits In

- **Depends on [`mise`](../mise/README.md)**: `mise` installs `pipx:docmancer` (with `embeddings-openai` and `pysocks`), and `docmancer/mise-env.toml` places `OPENAI_BASE_URL` and `OPENAI_API_KEY` into Mise's `conf.d` so `mise exec -- docmancer` behaves the same in terminals, IDEs, and sandboxes.
- **Extends [`junie`](../junie/README.md)**: Installs `~/.junie/skills/docmancer/SKILL.md` so Junie knows when and how to search or index docs before working with external libraries.
- **Works inside [`safehouse`](../safehouse/README.md)**: `safehouse/junie-local.sb` grants sandboxed Junie sessions read/write access to `~/.docmancer`, letting the agent query and refresh the index safely from inside the sandbox.

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
   - **Index**: `sqlite` storing metadata in `./docmancer.db` and extracted pages in `./extracted` (resolved relative to `~/.docmancer/`, not the working directory; `docmancer docs ...` falls back to `~/.docmancer/docmancer.yaml` whenever a directory lacks its own `./docmancer.yaml`, or you can pass `--config ~/.docmancer/docmancer.yaml` to target the global index explicitly).
   - **Vector store**: `sqlite-vec` for local vector search without a separate vector database.
   - **Embeddings**: `openai`-compatible provider pointing to `embeddinggemma-2:740m` (`dimensions: 768`).
   - **Retrieval**: `local` profile (hybrid FTS5 + `sqlite-vec` dense retrieval by default).
2. **Mise environment injection (`mise-env.toml` → `~/.config/mise/conf.d/docmancer.toml`)**:
   - Sets `OPENAI_BASE_URL = "http://localhost:11434/v1"` and `OPENAI_API_KEY = "ollama"` inside Mise's `conf.d`.
   - Running `mise exec -- docmancer ...` always resolves the Mise-managed `pipx:docmancer` binary (installed with `embeddings-openai` and `pysocks`) along with those environment variables, even in non-interactive shells or IDE subshells where `~/.bash_profile` wasn't sourced.
3. **Junie Agent Skill (`skills/docmancer/SKILL.md` → `~/.junie/skills/docmancer/SKILL.md`)**:
   - Guides Junie through documentation-only lookup (`docs list`, `docs query` with `--budget`, `--format`, `--expand` / `--expand page`, and `docs add` / `docs sync` / `docs remove`), warns against `docmancer ask` (Shared Memory), and requires invoking `mise exec -- docmancer` rather than a bare binary on `PATH`.

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

Always run Docmancer through `mise exec -- docmancer`, and stick to `docmancer docs ...` for documentation lookup (not `docmancer ask`, which searches Shared Memory):

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
