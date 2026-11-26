# Docmancer Consolidation Research & Migration Notes

Inventory of repositories under `~/repositories/` that still use project-local Docmancer configurations, along with a staged plan to import missing documentation into the global `~/.docmancer/` index and remove local configs one repository at a time.

---

## 1. Current State (Where We Are At)

- **Global Docmancer setup (already deployed via `personal-agent-config`):**
  - Config: `docmancer/docmancer.yaml` -> `~/.docmancer/docmancer.yaml`
  - Mise environment: `docmancer/mise-env.toml` -> `~/.config/mise/conf.d/docmancer.toml`
  - Global skill: `docmancer/skills/docmancer/SKILL.md` -> `~/.junie/skills/docmancer/SKILL.md`
  - Global rule: `junie/rules/docmancer-first.md` -> `~/.junie/AGENTS.md`
  - Safehouse policy: `safehouse/policies/docmancer.sb` -> `~/.config/safehouse/junie-local.sb` (grants read/write access to `~/.docmancer`)
  - **Currently indexed globally** (`mise exec -- docmancer docs list` as of 2026-11-26):
    - `https://agent-safehouse.dev/docs`
    - `https://docs.digitalocean.com/`
    - `https://docmancer.dev/`
    - `https://mise.jdx.dev/`
- **Repository scan status:** Complete across `~/repositories/`. Exactly **two** repositories still have project-local `docmancer.yaml` configs and `.docmancer/` documentation databases:
  1. `~/repositories/personal/microvm-web-hosting`
  2. `~/repositories/personal/microboat`
- **Clarification on `~/repositories/personal/personal-agent-config`:** Contains `.docmancer/project.json` and `.docmancer/state/delivery.json` (Docmancer CLI Shared Memory state only), with no local `docmancer.yaml` or docs database. (`docmancer/docmancer.yaml` is the global template.)
- **Changes made so far:** None. No new sources have been imported globally yet, and no project-local files have been removed.

---

## 2. Repository Inventory

### 2.1 `~/repositories/personal/microvm-web-hosting`

#### Local Docmancer Files (all untracked in git; `/.junie/` is gitignored)

- **Config & database:**
  - `docmancer.yaml` (points at `./.docmancer/docmancer.db`, `./.docmancer/extracted`, and `./.docmancer/sqlite-vec.db`)
  - `.docmancer/` (`455M`: `docmancer.db`, `sqlite-vec.db`, `extracted/`, `project.json`, `state/`, `last-ingest-report.json`)
- **Wrappers & downloaded doc staging under `.estel-local/`:**
  - `.estel-local/bin/docmancer` and `.estel-local/agent-bin/docmancer`
  - `.estel-local/docs/`: `digitalocean/`, `digitalocean.sh`, `llms-download.php`, and empty `dagger/`
  - **Important (keep non-Docmancer tools):** `.estel-local/bin/` also contains `composer`, `dev`, `php`, and `shared`; `.estel-local/agent-bin/` also contains `composer` and `php`. Do not delete `.estel-local/` wholesale.
- **Junie instructions:**
  - `.junie/skills/docmancer.md` (references `.estel-local/agent-bin/docmancer --config ./docmancer.yaml`)
  - `.junie/rules/agent-commands.md` (documents `php`, `composer`, and `docmancer` wrappers; only the `docmancer` row, example, and notes should be removed)

#### Indexed Sources (9 top-level sources, 1,204 pages)

| Source | Pages | Indexed At | Global Status |
| --- | --- | --- | --- |
| `https://symfony.com/doc` | 500 | `2026-10-17T18:40:15+00:00` | Missing globally |
| `https://psalm.dev/docs` | 367 | `2026-10-17T20:11:25+00:00` | Missing globally |
| `.estel-local/docs/digitalocean` | 229 | `2026-10-18T00:31:09+00:00` | Already covered (`https://docs.digitalocean.com/`) |
| `https://caddyserver.com/docs` | 40 | `2026-10-18T21:16:54+00:00` | Missing globally |
| `https://www.php-fig.org/psr` | 32 | `2026-10-17T19:13:23+00:00` | Missing globally |
| `https://frankenphp.dev/docs` | 28 | `2026-10-17T20:50:29+00:00` | Missing globally |
| `https://www.php-fig.org/per` | 6 | `2026-10-17T19:18:18+00:00` | Missing globally (5 under `/per`, 1 under `/personnel`) |
| `https://docs.boat.dev` | 1 | `2026-10-28T21:36:36+00:00` | Missing globally (single-page index) |
| `https://docs.dagger.io` | 1 | `2026-10-17T18:57:59+00:00` | Missing globally (single-page index) |

---

### 2.2 `~/repositories/personal/microboat`

#### Local Docmancer Files (all untracked in git; `.junie/` is gitignored)

- **Config & database:**
  - `docmancer.yaml` (points at `./.docmancer/docmancer.db`, `./.docmancer/extracted`, and `./.docmancer/sqlite-vec.db`)
  - `.docmancer/` (`357M`: `docmancer.db`, `docmancer.db-shm`, `docmancer.db-wal`, `sqlite-vec.db`, `extracted/`, `last-ingest-report.json`)
- **Wrappers & downloaded doc staging under `.estel-local/`:**
  - `.estel-local/bin/docmancer` and `.estel-local/agent-bin/docmancer`
  - `.estel-local/docs/`: `digitalocean/`, `digitalocean.sh`, `llms-download.php`, `nodejs/`
  - **Important (keep non-Docmancer tools):** `.estel-local/bin/` also contains `microboat`, `microboat-server`, `node`, `shared`, and `yarn`. Do not delete `.estel-local/` wholesale.
- **Junie instructions:**
  - `.junie/skills/docmancer.md` (references `.estel-local/agent-bin/docmancer --config ./docmancer.yaml`)

#### Indexed Sources (4 top-level sources, 370 pages)

| Source | Pages | Indexed At | Global Status |
| --- | --- | --- | --- |
| `.estel-local/docs/digitalocean` | 229 | `2026-10-29T01:14:21+00:00` | Already covered (`https://docs.digitalocean.com/`) |
| `https://www.typescriptlang.org/docs` | 70 | `2026-10-29T14:28:25+00:00` | Missing globally |
| `.estel-local/docs/nodejs` | 70 | `2026-10-29T14:16:40+00:00` | Missing globally (local markdown dump; prefer `https://nodejs.org/docs/latest/api/` or `https://nodejs.org/api/` if importing globally) |
| `https://docs.boat.dev` | 1 | `2026-11-24T18:37:04+00:00` | Missing globally (single-page index) |

---

## 3. Candidate Docs to Import Globally

Excluding `.estel-local/docs/digitalocean` (already globally indexed via `https://docs.digitalocean.com/`), the unique candidate sources are:

- **PHP / Web Stack (from `microvm-web-hosting`):**
  - `https://symfony.com/doc`
  - `https://psalm.dev/docs`
  - `https://caddyserver.com/docs`
  - `https://frankenphp.dev/docs`
  - `https://www.php-fig.org/psr`
  - `https://www.php-fig.org/per`
- **Node.js / TypeScript (from `microboat`):**
  - `https://www.typescriptlang.org/docs`
  - Node.js API docs (`https://nodejs.org/docs/latest/api/` or `https://nodejs.org/api/`, replacing the local `.estel-local/docs/nodejs` dump)
- **Containers / MicroVMs (check if full crawl or skip):**
  - `https://docs.boat.dev` (only 1 page indexed locally in both repos)
  - `https://docs.dagger.io` (only 1 page indexed locally in `microvm-web-hosting`)

---

## 4. Next Steps (Staged Execution Plan)

Work through global import first, then migrate repositories **one at a time** so each project can be verified before touching the next.

### Step 1: Import Approved Sources Into Global Docmancer

- **Import strategy preference:** Always try `--strategy llms.txt` first when importing docs into the global store. Avoid `llms-full.txt` or other discovery strategies (such as `sitemap.xml` or `nav-crawl`) unless `llms.txt` is unavailable and another strategy is unavoidable for a specific source.

1. Decide which candidate URLs above to keep globally (and whether to re-crawl `docs.boat.dev` / `docs.dagger.io` or skip them).
2. From `personal-agent-config` (or any directory without a local `docmancer.yaml`), import each chosen source using `--strategy llms.txt` first:
   ```bash
   mise exec -- docmancer docs add --strategy llms.txt <url>
   ```
   Only fall back to another strategy (avoiding `llms-full.txt` unless unavoidable) if `--strategy llms.txt` is not available for that source.
3. Verify global availability and retrieval:
   ```bash
   mise exec -- docmancer docs list
   mise exec -- docmancer docs query "<library> <topic>" --budget 1200
   ```

### Step 2: Clean Up `microboat` First & Verify

Start with `microboat` because it has no `.junie/rules/agent-commands.md` dependencies and keeps cleanup minimal.

1. **Remove local Docmancer artifacts (preserve non-Docmancer `.estel-local/bin/*`):**
   - `docmancer.yaml`
   - `.docmancer/`
   - `.estel-local/bin/docmancer`
   - `.estel-local/agent-bin/docmancer` (if `.estel-local/agent-bin/` becomes empty, remove the empty directory)
   - `.estel-local/docs/` (`digitalocean/`, `digitalocean.sh`, `llms-download.php`, `nodejs/`)
   - `.junie/skills/docmancer.md`
2. **Verify inside `~/repositories/personal/microboat`:**
   - Confirm `mise exec -- docmancer docs list` resolves `~/.docmancer/docmancer.yaml` and shows the global sources (including TypeScript / Node.js).
   - Confirm `mise exec -- docmancer docs query "typescript ..." --budget 1200` succeeds from the repo root (and inside `junie-safehouse` if testing sandboxed agent runs).
   - Confirm `.estel-local/bin/microboat`, `.estel-local/bin/node`, `.estel-local/bin/yarn`, and project tests/scripts still run cleanly.

### Step 3: Clean Up `microvm-web-hosting` Second & Verify

1. **Remove local Docmancer artifacts (preserve `php`, `composer`, `dev`, `shared`):**
   - `docmancer.yaml`
   - `.docmancer/`
   - `.estel-local/bin/docmancer`
   - `.estel-local/agent-bin/docmancer` (keep `php` and `composer` in `.estel-local/agent-bin/`)
   - `.estel-local/docs/` (`digitalocean/`, `digitalocean.sh`, `llms-download.php`, `dagger/`)
   - `.junie/skills/docmancer.md`
2. **Update `.junie/rules/agent-commands.md`:**
   - Remove the `docmancer` row from the commands table, the `.estel-local/agent-bin/docmancer` usage example, and the two `docmancer` bullets under "Important details", leaving `php` and `composer` intact.
3. **Verify inside `~/repositories/personal/microvm-web-hosting`:**
   - Confirm `mise exec -- docmancer docs list` resolves `~/.docmancer/docmancer.yaml` and shows the global PHP/Symfony/Psalm/Caddy/FrankenPHP sources.
   - Confirm `mise exec -- docmancer docs query "symfony ..." --budget 1200` succeeds from the repo root (and inside `junie-safehouse`).
   - Confirm `.estel-local/agent-bin/php --version`, `.estel-local/agent-bin/composer --version`, and project tests still work cleanly.
