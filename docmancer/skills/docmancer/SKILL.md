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

## When to use

- Before implementing features or fixes involving external frameworks, libraries, or SDKs
- When checking exact API signatures, configuration options, CLI flags, or conventions
- When unsure how an installed library works — check indexed sources first, and index missing docs if needed

## Lookup workflow

### 1. Ask a focused question

Start with `mise exec -- docmancer ask` to get relevant sections from indexed documentation within a token budget:

```bash
# Scoped to a specific source (faster, higher precision)
mise exec -- docmancer ask "how do migrations work" --source <source> --json --budget 2400

# Across all indexed sources
mise exec -- docmancer ask "how to configure authentication middleware" --json --budget 2400
```

Flags:
- `--source <name>` — restrict search to a single indexed source
- `--budget <tokens>` — cap response size (default `2400`; use `1200` for quick checks, `4000` for deep dives)
- `--expand adjacent` — include neighboring sections around each match for fuller context
- `--json` — structured output with `section_id`, `source`, `title`, `url`, `score`, `content`

### 2. Inspect exact sections or pages

When `mise exec -- docmancer ask` identifies a relevant hit and you need the full text or surrounding context:

```bash
# Inspect a specific section by ID
mise exec -- docmancer section <section_id> --json

# Inspect a full page by URL or path
mise exec -- docmancer page <url_or_path> --json
```

### 3. Check indexed sources

Before querying (or if a query returns no hits), list what documentation is already available:

```bash
mise exec -- docmancer docs list
```

### 4. Index missing documentation

If a needed library or tool is not yet indexed, fetch and index its docs before proceeding:

```bash
# Index from a documentation website (prefers llms.txt / sitemap, crawls links)
mise exec -- docmancer docs add <url> --name <source-name>

# Index from a local directory or git repository
mise exec -- docmancer docs add /path/to/docs --name <source-name>

# Refresh an existing source when docs have changed
mise exec -- docmancer docs refresh <source-name>
```

Check supported options with `mise exec -- docmancer docs add --help` if you need filtering (e.g., path prefixes or page limits).

## Best practices

1. **Always check sources first or scope with `--source`** when you know which library you are asking about.
2. **Use `--json` and `--budget`** so responses stay concise and easy to parse without blowing context limits.
3. **Prefer `ask` -> `section`/`page` drill-down** rather than pulling entire documentation pages upfront.
4. **Never guess undocumented APIs** — if it is not in the indexed docs, check `mise exec -- docmancer docs list` and index the official docs first.
5. **Never rely on a bare `docmancer` binary on PATH** — always run `mise exec -- docmancer ...`.
