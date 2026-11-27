# Docmancer

This system configures [Docmancer](https://docmancer.dev/) for local documentation indexing and search using SQLite and local [Ollama](https://ollama.com/) embeddings, and installs a Junie skill so the agent checks indexed docs before guessing APIs.

## Why I Use It

Coding agents guess at APIs, config schemas, and CLI flags from stale training data all the time. Indexing official docs locally lets Junie query current references inside a tight token budget instead of hallucinating or pulling raw web pages into context.

Everything stays local (SQLite, `sqlite-vec`, and Ollama's `embeddinggemma-2:740m`), so there's no per-query embedding bill or external vector database to run. Queries also stick strictly to `docmancer docs`, leaving Docmancer's Shared Memory (`docmancer ask`) unused.

## How It Fits In

- **`mise`:** [`mise`](../mise/README.md) installs `pipx:docmancer` (with its OpenAI embeddings and SOCKS dependencies) and loads `docmancer/mise-env.toml` so `mise exec -- docmancer` always points at local Ollama, even in IDE subshells or sandboxes where `~/.bash_profile` wasn't sourced.
- **`junie`:** Drops `~/.junie/skills/docmancer/SKILL.md` in place so Junie knows when and how to search or index docs before reading third-party source files.
- **`safehouse`:** [`safehouse`](../safehouse/README.md) gives sandboxed Junie sessions read/write access to `~/.docmancer`, letting the agent query and refresh the index from inside the sandbox.

## Prerequisites

1. **Install `mise` first** (since it provides `~/bin/mise` and `pipx:docmancer`):
   ```bash
   bin/install mise
   ```
2. **Pull the embedding model in Ollama** (and make sure Ollama is running locally):
   ```bash
   ollama pull embeddinggemma-2:740m
   ```

## Quick Start

```bash
# Sync Docmancer config, Mise env vars, and the Junie skill
bin/install docmancer

# Verify Mise env vars, docmancer binary, and required Python extras
bin/doctor docmancer
```

## Common Commands

Always run Docmancer through `mise exec -- docmancer` (not bare `docmancer`) so Mise injects the local Ollama `OPENAI_*` environment variables, and stick to `docmancer docs` rather than `docmancer ask`:

```bash
# List indexed documentation sources (add --all for individual pages/files)
mise exec -- docmancer docs list
mise exec -- docmancer docs list --all

# Index a docs site, GitHub repo, or local directory
mise exec -- docmancer docs add https://example.com/docs
mise exec -- docmancer docs add https://github.com/owner/repo
mise exec -- docmancer docs add /path/to/docs

# Search indexed docs within a token budget (include the tool/library name)
mise exec -- docmancer docs query "example routing configuration" --budget 2400

# Expand adjacent sections or full pages for top matches
mise exec -- docmancer docs query "example routing configuration" --limit 2 --budget 3000 --expand
mise exec -- docmancer docs query "example routing configuration" --limit 1 --budget 4000 --expand page

# Get JSON output instead of text
mise exec -- docmancer docs query "example routing configuration" --format json

# Refresh all sources or a single source
mise exec -- docmancer docs sync
mise exec -- docmancer docs sync https://example.com/docs

# Remove an indexed source
mise exec -- docmancer docs remove https://example.com/docs
```

## Files

| Repo Source | Target Path | What It Is For |
| --- | --- | --- |
| `docmancer/docmancer.yaml` | `~/.docmancer/docmancer.yaml` | SQLite index, `sqlite-vec`, Ollama embedding model, and retrieval profile. |
| `docmancer/mise-env.toml` | `~/.config/mise/conf.d/docmancer.toml` | Points `OPENAI_BASE_URL` and `OPENAI_API_KEY` at local Ollama (`localhost:11434`). |
| `docmancer/skills/docmancer/SKILL.md` | `~/.junie/skills/docmancer/SKILL.md` | Junie skill instructions for searching and indexing docs. |
| `docmancer/hooks/doctor` | *(hook)* | Checks Mise, env vars, `docmancer --version`, and Python extras. |
