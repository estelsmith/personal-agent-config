# Graphify Research Notes

Research gathered on [`Graphify-Labs/graphify`](https://github.com/Graphify-Labs/graphify) (evaluated at `v8` / PyPI `graphifyy==0.9.120` on 2026-11-26) to determine where it fits in `personal-agent-config`, what languages it supports, and how to isolate project graphs.

See [`implementation-plan.md`](./implementation-plan.md) for the concrete `personal-agent-config` integration plan (including the Mise `pipx:graphifyy` Python `3.14` pinning quirk).

---

## 1. Where Graphify Fits in the Stack

Graphify is a **codebase & corpus knowledge-graph tool**, not a temporal or auto-reconciling state memory system. It parses code across 25+ languages via `tree-sitter` ASTs (plus optional LLM extraction for Markdown, PDFs, images, and videos) into a persistent NetworkX graph (`graphify-out/graph.json`), `GRAPH_REPORT.md`, an optional `wiki/`, and an MCP server (`graphify/serve.py`, entrypoint `graphify-mcp`).

It complements the other memory/knowledge layers rather than replacing them:

| Concern | Best-Fit Tool | Notes |
| --- | --- | --- |
| **External library / CLI / vendor docs** | **Docmancer (`docmancer docs`)** | Already configured via SQLite + `sqlite-vec` + Ollama `embeddinggemma-2:740m`. |
| **Codebase structure & symbol relationships** | **Graphify** | AST-driven `graphify update` / `--watch` keeps `graph.json` synchronized with files on disk at zero LLM cost; exposes `query_graph`, `affected`, `get_node`, `get_neighbors`, `shortest_path`, `god_nodes`, `get_pr_impact`. |
| **Evolving "current state" / temporal memory** | **Dedicated temporal memory (e.g. Graphiti/Zep or Mem0/Letta)** | Tracks fact validity intervals (`valid_from` / `invalid_at`) or runs `ADD`/`UPDATE`/`DELETE` consolidation so new observations supersede stale state. |
| **Lightweight repo/session ground truth** | **`AGENTS.md`, `bin/doctor`, `session-history`** | Best for small repos like `personal-agent-config` where plain `grep` and file reads are faster than querying a graph. |

### Why Graphify's Built-In "Work Memory" Is Not Temporal State Memory

Graphify `v8` includes `graphify save-result` (`graphify/ingest.py`) and `graphify reflect` (`graphify/reflect.py`):
- `save-result` writes Q&A entries to `graphify-out/memory/*.md` with optional `--outcome` (`useful`, `dead_end`, `corrected`) and `--correction`.
- `reflect` deterministically aggregates outcomes into `graphify-out/reflections/LESSONS.md` with time-decayed scoring and prunes citations whose nodes were removed from `graph.json`.

Limitations for general "current state" tracking:
- No bi-temporal validity (`valid_from` / `invalid_at`) and no automated LLM fact-reconciliation loop (`ADD`/`UPDATE`/`DELETE`).
- `save-result` is CLI-only (not exposed as an MCP tool in `graphify/serve.py`).
- Designed to score which graph nodes/queries were useful or dead ends, not operational or architectural state across sessions.

---

## 2. Language Support (`graphifyy 0.9.120`)

### TypeScript, JavaScript, and Python: Full First-Class Support

- **TypeScript (`tree-sitter-typescript` `0.23.2`)**
  - Files: `.ts`, `.tsx`, `.mts`, `.cts`, plus `<script lang="ts">` inside `.vue`, `.svelte`, and `.astro`.
  - Extracts classes, `abstract` classes/methods, interfaces, enums, type aliases, functions, generators, methods, decorators, ESM `import`/`export` (including `import type`, `export type *`, `import x = require(...)`), `tsconfig.json` `paths`/`baseUrl` resolution, `new` expressions, JSX/TSX component edges, and typed receiver member calls.
- **JavaScript (`tree-sitter-javascript` `0.25.0`)**
  - Files: `.js`, `.jsx`, `.mjs`, `.cjs`, plus `.ejs`, `.vue`, `.svelte`, `.astro`, and inline `<script>` tags inside `.php` files.
  - Extracts classes, functions, generators, methods, arrow/inline closures, ESM + CommonJS (`require()`, barrel re-exports, dynamic `import()`), `package.json` `#` subpath imports, `jsconfig.json` `baseUrl`, JSX component edges, and `this.`/receiver calls.
- **Python (`tree-sitter-python` `0.25.0`)**
  - Files: `.py` (with `.pyi` stub awareness for import resolution).
  - Extracts classes, functions, methods, decorators, `import`/`from ... import` (including relative & `__init__.py` resolution), inherited method calls, typed receiver / `self` / `@pytest.fixture` / factory-injected calls, property reads, and Python 3.12+ `type` statements / PEP 695 type parameters.

### PHP 8.5: Mostly Supported, With Specific Grammar Gaps

Graphify `0.9.120` caps `tree-sitter-php>=0.23,<0.25` in `pyproject.toml` (locked at `0.24.1` in `uv.lock`, released August 2025 before PHP 8.5 shipped in November 2025).

- **Files:** `.php` (`extract_php`), inline `<script>` JS blocks inside `.php`, and Laravel `.blade.php` templates (`graphify/extractors/blade.py` for `@extends`, `@include`, `<livewire:>`, `wire:click`). Non-standard extensions like `.phtml` or `.inc` require a `.graphifyrc` override.
- **Extracted constructs:** `class`, `interface`, `trait`, PHP 8.1+ `enum` (`case_of` edges), functions/methods/closures/arrow functions, `namespace`/`use` imports, `extends`/`implements`/trait `use` (`mixes_in`), constructor property promotion, typed `$this->`/`$obj->` calls, static `::` calls, class constant references, and `new Foo(...)` edges.
- **PHP 8.4 / 8.5 syntax that already works in `0.24.1`:**
  - Pipe operator (`|>`)
  - Attributes (e.g. `#[\NoDiscard]`), closures in `const` expressions
  - PHP 8.4 property hooks (`property_hook_list`)
  - Asymmetric visibility on regular class properties (`public private(set) string $x`)
- **PHP 8.4 / 8.5 syntax that triggers `tree-sitter-php` `0.24.1` parse errors:**
  - PHP 8.5 `clone` with arguments: `clone($obj, ['prop' => $val])` (grammar support added in `tree-sitter-php` `0.25.1`).
  - Asymmetric visibility in constructor property promotion: `__construct(public private(set) string $x)` (added in `tree-sitter-php` `0.25.0`).
  - `final` in constructor property promotion: `__construct(final public string $x)`.
- **Failure behavior:** Tree-sitter recovers past `ERROR` nodes rather than aborting the whole run, so surrounding declarations in a file usually still extract, though nodes inside the broken region can be lost and Graphify logs a `may be partially extracted` warning. Upgrading `tree-sitter-php` to `0.25.x` is blocked by Graphify's `<0.25` constraint until upstream bumps it.

---

## 3. Project-Local vs. Global Graph Isolation

`~/.graphify/global-graph.json` (`graphify/global_graph.py`) is **not** a directory of isolated per-project graphs; it is a **single merged NetworkX graph**. Using it for unrelated projects causes cross-project pollution:

1. **External dependency nodes merge globally:** Nodes without a `source_file` (libraries/packages) are deduplicated by `label` across all added repos, with edges from every repo rewired to the shared node.
2. **Cross-repo calls are synthesized:** `link_cross_repo_member_calls()` (`graphify/cross_repo_calls.py`) attempts to connect unresolved method calls in repo A to matching type declarations in repo B.
3. **Queries cannot be scoped by repo:** Neither `graphify query` (`graphify/cli.py`) nor the MCP `query_graph` tool (`graphify/serve.py`) accepts a `--repo` / `repo_tag` filter. Queries, BFS/DFS traversals, `god_nodes`, and `affected` search the entire merged graph.

### Recommended Isolation Patterns

- **Keep `global-graph.json` strictly for genuinely coupled repos** (e.g., frontend + backend + shared SDKs where cross-repo call tracing is desired).
- **For independent projects, isolate graphs using either:**
  1. **Per-repo `graphify-out/graph.json` + multi-project MCP (`graphify-mcp`):** Every MCP tool (`query_graph`, `affected`, `get_node`, `get_neighbors`, etc.) accepts an optional `project_path` parameter that resolves `<project_path>/graphify-out/graph.json` into an isolated per-path cache (`_GraphContextCache`). `graphify/serve.py` can run with no default graph loaded at startup.
  2. **Centralized per-project storage via `GRAPHIFY_OUT` (`graphify/paths.py`):** Setting `GRAPHIFY_OUT` (e.g. `~/.graphify/projects/<repo-name>`) alongside `.graphify_root` stores graphs outside git working trees on disk **without** merging projects into `global-graph.json`.
