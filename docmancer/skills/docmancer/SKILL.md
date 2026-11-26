---
name: docmancer
description: >
    ALWAYS consult indexed documentation via Docmancer before coding with external
    libraries, frameworks, or SDKs. Use Docmancer to look up APIs, patterns,
    configuration, and conventions from project-relevant docs (and index missing
    libraries on demand), instead of guessing or relying on stale training knowledge.
---

# Docmancer: Documentation Lookup

Executable: `mise exec -- docmancer`

**Always invoke Docmancer via `mise exec -- docmancer` instead of calling a bare system `docmancer` binary.** Running through `mise exec` ensures the Mise-managed package and environment (`OPENAI_BASE_URL`, `OPENAI_API_KEY`) are used regardless of shell activation.

**Use `docmancer docs ...` strictly for documentation lookup.** Never use `docmancer ask` (which searches Shared Memory, not library docs) or non-existent `section` / `page` subcommands.

**Config discovery:** When run from a project directory without a local `./docmancer.yaml`, `docmancer docs ...` automatically uses `~/.docmancer/docmancer.yaml` (whose relative `db_path` and `extracted_dir` resolve against `~/.docmancer/`, not the current working directory). Pass `--config ~/.docmancer/docmancer.yaml` if a repo has its own `./docmancer.yaml` and you want the global docs index instead.

## When to use

- Before implementing features or fixes involving external frameworks, libraries, or SDKs
- When checking exact API signatures, configuration options, CLI flags, or conventions
- When unsure how an installed library works — check indexed sources first, and index missing docs if needed

## Lookup workflow

### 1. Check indexed sources

List what documentation is already available before querying (or if a query returns no hits):

```bash
# List top-level indexed docsets/sources
mise exec -- docmancer docs list

# List every stored page or file source
mise exec -- docmancer docs list --all
```

### 2. Query indexed documentation

Search indexed docs within a token budget using `mise exec -- docmancer docs query`:

```bash
# Compact markdown context pack (default format, default hybrid mode)
mise exec -- docmancer docs query "safehouse append profile configuration" --budget 2400

# Structured JSON output with source, section_title, score, and text
mise exec -- docmancer docs query "mise exec env conf.d" --limit 5 --budget 2400 --format json

# Fall back to lexical/remaining signals if local Ollama embeddings are unavailable
mise exec -- docmancer docs query "docmancer configuration" --allow-degraded
```

Note on scoping: `docmancer docs query` does **not** have a `--source` flag in `0.9.17`. Always include the library, framework, or tool name in the query string so results stay focused across multiple indexed docsets.

Key flags:
- `--budget <tokens>` — cap estimated output tokens (default `2400`; use `1200` for quick checks, `4000` for deep dives)
- `--limit <n>` — maximum sections returned (default `8`)
- `--format [markdown|json]` — output format (default `markdown`; use `--format json` for structured output — `--json` does not exist)
- `--mode [lexical|dense|sparse|hybrid]` — retrieval mode (default reads `retrieval.default_mode` from config, which is `hybrid`)
- `--allow-degraded` — fall back to remaining signals (e.g. SQLite FTS5 lexical search) if a retriever errors instead of failing
- `--explain` — show per-retriever rank contributions (`dense#...`, `lexical#...`)
- `--config <path>` — explicit path to `docmancer.yaml`

### 3. Expand surrounding sections or full pages

When `docs query` identifies a relevant hit and you need neighboring sections or the full page, re-run `docs query` with `--expand`:

```bash
# Include adjacent sections around each match
mise exec -- docmancer docs query "docmancer router recipes" --limit 2 --budget 3000 --expand

# Include the full page for top match(es) — place 'page' right after '--expand'
mise exec -- docmancer docs query "docmancer router recipes" --limit 1 --budget 4000 --expand page
```

### 4. Index or refresh documentation

If a needed library or tool is not yet indexed, fetch and index its docs before proceeding (note: there is no `--name` flag; sources are identified by URL or path):

```bash
# Index from a documentation website (auto tries llms.txt then sitemap.xml)
mise exec -- docmancer docs add <url>

# Index from a GitHub repository (README + docs/)
mise exec -- docmancer docs add https://github.com/<owner>/<repo>

# Index from a local directory or file
mise exec -- docmancer docs add /path/to/docs

# Refresh all indexed sources or a single source when docs have changed
mise exec -- docmancer docs sync
mise exec -- docmancer docs sync <url-or-path>

# Remove an indexed source
mise exec -- docmancer docs remove <url-or-path>
```

Check `mise exec -- docmancer docs add --help` for filtering and crawler options (such as `--provider`, `--strategy`, `--max-pages`, `--browser`, `--include`, `--exclude`, `--format`, and `--recreate`).

## Best practices

1. **Always use `docmancer docs ...`** — never invoke `docmancer ask` (Shared Memory) or nonexistent `section`/`page` commands.
2. **Include the library or tool name in every `docs query`** since `docs query` searches across all indexed docsets without a `--source` flag.
3. **Start compact (`--budget 1200`–`2400`) and drill down with `--expand` / `--expand page`** rather than pulling entire pages upfront.
4. **Use `--allow-degraded` if Ollama is offline** so FTS5 lexical retrieval can still answer immediately.
5. **Never guess undocumented APIs** — check `mise exec -- docmancer docs list` and index the official docs with `docs add` first.
6. **Never rely on a bare `docmancer` binary on PATH** — always run `mise exec -- docmancer ...`.
