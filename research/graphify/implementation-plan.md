# Graphify Planned Implementation Notes

Planned integration design for adding Graphify (`graphifyy`) to `personal-agent-config` when ready to implement.

---

## 1. Mise Installation & Python `3.14` Pinning Quirk

### The Quirk
- `mise/tools.toml` currently pins global `python = "3.15"` (with `uv = "0.13.10"`).
- `graphifyy` (`0.9.120`) declares `requires-python = ">=3.11.5,<3.15"` in `pyproject.toml`.
- Mise's `pipx:` (alias for the `pypi` backend) uses `uv` and passes `--python <global python>` (`3.15`) by default. Running a bare `mise use --global pipx:graphifyy` **fails dependency resolution** instead of automatically picking Python `3.14`.

### The Fix (No Global Python Downgrade Needed)
Use Mise's per-tool `python` option so Mise provisions `python@3.14` privately for `pipx:graphifyy` while keeping the global shell `python` at `3.15`:

- **Target `mise/tools.toml` entry:**
  ```toml
  "pipx:graphifyy" = { version = "0.9.120", python = "3.14", extras = ["mcp"] }
  ```
  - Optional extras to evaluate before finalizing:
    - `mcp` (recommended if registering `graphify-mcp` with Junie; pulls `mcp`, `starlette`, `anyio`).
    - `leiden` (pulls `graspologic-native>=1.3.1,<2` for Python `>=3.13` Leiden community detection).
    - `watch` (pulls `watchdog` if using `graphify --watch`).
- **Equivalent manual CLI:**
  ```bash
  mise use --global 'pipx:graphifyy[extras=mcp,python=3.14]@0.9.120'
  ```
- **Repo compatibility (`mise/hooks/_mise.py`):**
  - `ToolSpec.to_cli_spec()` already formats table entries into `pipx:graphifyy[extras=mcp,python=3.14]@0.9.120`.
  - `_parse_fallback_toml_value()` handles inline tables and string arrays if `bin/install mise` runs under `/usr/bin/python3` without `tomllib`.
  - `check_global_tools()` verifies `mise ls --global --json` by `requested_version` (`0.9.120`).

---

## 2. Proposed Repo Layout & Cross-System Coupling

Following the existing `docmancer/` system pattern (`docmancer/manifest`, `docmancer/hooks/doctor`, `docmancer/skills/docmancer/SKILL.md`):

### New `graphify/` System (Optional Dedicated System)
- `graphify/README.md`: Purpose, prerequisites, commands (`mise exec -- graphify ...`), and file mapping.
- `graphify/manifest`:
  ```text
  # <mode> <source> <target> [sync|seed]
  0644 skills/graphify/SKILL.md ~/.junie/skills/graphify/SKILL.md
  ```
- `graphify/skills/graphify/SKILL.md`: Junie skill explaining:
  - Always invoke via `mise exec -- graphify ...` (never rely on a bare binary on `PATH`).
  - Prefer graph tools (`query_graph`, `affected`, `get_node`, `get_neighbors`, `shortest_path`, `god_nodes`, `get_pr_impact`) **only when a repo already has a graph** (or is large enough to benefit from one); for small repos like `personal-agent-config`, stick to direct search/reads.
  - Keep AST graph fresh with `mise exec -- graphify update` (or `--update`).
  - Keep unrelated projects isolated (do not dump unrelated repos into `~/.graphify/global-graph.json`).
- `graphify/hooks/doctor` (`0755`, stdlib-only Python, `[FAIL] ` prefix on errors):
  - Check `~/bin/mise` exists and is executable.
  - Run `mise exec -- graphify --version` (and `mise exec -- graphify-mcp --help` if `mcp` extra is included).
  - Resolve the tool's shebang interpreter via `mise which graphify` (same pattern as `docmancer/hooks/doctor`) and verify Python `<3.15` and any required extras (e.g. `import mcp` when `extras = ["mcp"]` is configured).

### Cross-System Updates
1. **`mise/tools.toml`:** Add `"pipx:graphifyy" = { version = "0.9.120", python = "3.14", extras = ["mcp"] }`.
   - Note: `discover_systems()` runs alphabetically (`docmancer`, `graphify`, `junie`, `litellm-proxy`, `mise`, `safehouse`), so `mise` must still be installed before `graphify` on a fresh machine (aligns with the dependency DAG item in `wishlist.md`).
2. **`junie/`:**
   - Optional `junie/rules/graphify.md` (only if we want an always-on global rule in `~/.junie/AGENTS.md` reminding Junie to check for `graphify-out/graph.json` or the Graphify MCP before broad codebase grep; otherwise keep guidance purely inside the `graphify` skill to avoid prompt bloat).
3. **`safehouse/junie-local.sb`:**
   - Per-repo `graphify-out/` already sits inside the writable project workspace.
   - Add `(home-literal "/.graphify")` (`file-read-metadata`) and `(home-subpath "/.graphify")` (`file-read* file-write*`) **only if** we decide to store centralized graphs under `~/.graphify/projects/<repo>` via `GRAPHIFY_OUT` or use `~/.graphify/global-graph.json` for coupled multi-repo setups.
4. **Global gitignore (`~/.gitignore_global`, if desired):**
   - Decide whether `graphify-out/` should be ignored per-repo or globally so generated `graph.json` / `GRAPH_REPORT.md` artifacts are not accidentally committed in repos that don't check them in.

---

## 3. Junie Integration Details (CLI vs. MCP)

Graphify ships built-in presets for Claude Code, Codex, OpenCode, Cursor, Gemini CLI, etc., **but has no native Junie preset** (`graphify install` should not be relied upon to configure `~/.junie/`).

Two integration options:
- **Option A: Skill + CLI (`mise exec -- graphify ...`)**
  - Simplest starting point; zero persistent MCP server config.
  - Junie runs `mise exec -- graphify query ...` / `mise exec -- graphify update` on demand when `graphify-out/graph.json` is present.
- **Option B: Multi-project MCP (`mise exec -- graphify-mcp`) + Skill**
  - `graphify-mcp` (`graphify.serve:_main`) supports multi-project isolation via the `project_path` parameter on every MCP tool, loading `<project_path>/graphify-out/graph.json` into an isolated per-path cache (`_GraphContextCache`) with no default graph required at startup.
  - Requires wiring `mise exec -- graphify-mcp` into Junie's MCP configuration (either managed via `junie/` or documented in `graphify/README.md`).

---

## 4. Verification Plan (When Implementing)

1. Run `python3 -m unittest discover -s tests -v` after adding coverage in `tests/test_cli.py`:
   - `mise/tools.toml` parsing & `ToolSpec.to_cli_spec` output for `pipx:graphifyy` with `python = "3.14"`.
   - `graphify` manifest install (`~/.junie/skills/graphify/SKILL.md`) and `graphify/hooks/doctor` pass/fail paths using fake `mise` shims.
2. Preview with `bin/install --dry-run mise graphify`.
3. Run `bin/install mise graphify` and `bin/doctor mise graphify` on the live host to verify `uv` resolves `pipx:graphifyy` under Python `3.14` while `mise exec -- python --version` remains `3.15`.
4. Check `git status` / `git diff` to verify no stray secrets or `graphify-out/` artifacts remain tracked.

---

## 5. Open Decisions to Revisit Before Implementing

- [ ] **Extras selection:** Just `["mcp"]`, or also `["leiden", "watch"]`?
- [ ] **Integration mode:** Start with CLI + Skill only (Option A), or configure `graphify-mcp` in Junie immediately (Option B)?
- [ ] **Graph location:** Per-repo `graphify-out/` (isolated, simple `project_path` MCP support) vs. centralized `~/.graphify/projects/<repo>` via `GRAPHIFY_OUT` (keeps working trees clean, requires `safehouse/junie-local.sb` access to `~/.graphify`)?
- [ ] **Always-on rule vs. skill-only:** Should `junie/rules/` stay lean (skill-only) or add a short pointer rule like `junie/rules/docmancer-first.md`?
- [ ] **PHP 8.5 caveat check:** Test Graphify extraction against a real PHP 8.5 repo first if PHP 8.5 `clone($obj, [...])` or promoted `final`/asymmetric visibility is heavily used (see [`README.md`](./README.md#php-85-mostly-supported-with-specific-grammar-gaps)).
