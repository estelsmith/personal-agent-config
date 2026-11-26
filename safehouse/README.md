# Safehouse

This system sandboxes Junie CLI sessions on macOS using [Agent Safehouse](https://agent-safehouse.dev/) (`sandbox-exec`). It installs a wrapper script (`~/bin/junie-safehouse`), a machine-local Seatbelt profile (`~/.config/safehouse/junie-local.sb`), and a JetBrains ACP server configuration (`~/.jetbrains/acp.json`) so both terminal runs and JetBrains IDEs launch Junie inside the same sandbox.

## Why I Use It

Autonomous coding agents run shell commands and edit files, so I don't want them having unrestricted access to the rest of my machine. Sandboxing restricts writes to the active project and explicit agent state directories while blocking access to unrelated repos, browser data, SSH keys, and host secrets.

Pointing both my terminal workflow and JetBrains IDE's `~/.jetbrains/acp.json` at the same `junie-safehouse` wrapper guarantees identical boundaries no matter where Junie runs.

## How It Fits In

`safehouse` is the execution boundary that ties the rest of the stack together safely at runtime:

- [`junie`](../junie/README.md) & [`docmancer`](../docmancer/README.md): Grants read/write access to `~/.junie` (global `AGENTS.md`, skills, sessions) and `~/.docmancer` (local documentation index and embeddings), while allowing read access to `~/bin` and `~/.homebrew` so agents can run `mise exec -- docmancer` and [`mise`](../mise/README.md)-managed tools.
- [`litellm-proxy`](../litellm-proxy/README.md): Passes `LITELLM_MASTER_KEY` into the sandbox (`--env-pass=LITELLM_MASTER_KEY`) so Junie talks to the local proxy without ever seeing `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` in its environment.

## How It Works

```text
JetBrains IDE (~/.jetbrains/acp.json) or Terminal
   │  invokes ~/bin/junie-safehouse [--acp=true]
   ▼
~/.homebrew/bin/safehouse
   ├── --enable=docker
   ├── --add-dirs="~/.junie:~/.mcp-auth"            (read/write)
   ├── --add-dirs-ro="~/.local/bin:~/.local/share/junie:~/Applications/PhpStorm.app:~/mcp-servers"
   ├── --append-profile="~/.config/safehouse/junie-local.sb"
   └── --env-pass=LITELLM_MASTER_KEY
          │
          ▼
     ~/.local/bin/junie "$@"
```

- **Wrapper (`junie-safehouse` → `~/bin/junie-safehouse`)**: Launches `~/.local/bin/junie` through `~/.homebrew/bin/safehouse`, forwarding all CLI arguments (including `--acp=true`).
  - Grants read/write access to `~/.junie` (sessions, skills, logs) and `~/.mcp-auth`.
  - Grants read-only access to `~/.local/bin`, `~/.local/share/junie`, `~/Applications/PhpStorm.app`, and `~/mcp-servers`.
  - Enables Docker access (`--enable=docker`) and forwards `LITELLM_MASTER_KEY` from the host environment (`--env-pass=LITELLM_MASTER_KEY`) so Junie can talk to [`litellm-proxy`](../litellm-proxy/README.md).
- **Appended Seatbelt profile (`policies/*.sb` → `~/.config/safehouse/junie-local.sb`)**:
  - `safehouse/hooks/post-install` concatenates `safehouse/policies/*.sb` alphabetically and atomically writes `~/.config/safehouse/junie-local.sb` (`0644`):
  - `policies/desktop-apps.sb`: Blocks direct execution of macOS `.app` bundles under `/Applications`, `/System/Volumes/Data/Applications`, `/System/Applications`, `/System/Cryptexes/App/System/Applications`, and `~/Applications` (with carve-outs for `Docker.app/Contents/Resources/{bin,cli-plugins}` and `~/Applications/PhpStorm.app/Contents/{MacOS/phpstorm,jbr}` for the PhpStorm MCP server), and denies `lsopen`, `/usr/bin/open`, and `/usr/bin/osascript`.
  - `policies/docmancer.sb`: Allows read/write access to `~/.docmancer` (SQLite index, `sqlite-vec` database, extracted docs, and embeddings cache).
  - `policies/local-tools.sb`: Allows metadata and read access to `~/.homebrew`, `~/npm`, `~/bin`, and `~/.gitignore_global`.
- **JetBrains ACP registration (`acp.json` → `~/.jetbrains/acp.json`)**:
  - Registers the `junie-safehouse` agent server with `--acp=true` for JetBrains IDEs.
  - `safehouse/acp.json` uses `${HOME}/bin/junie-safehouse`; `safehouse/hooks/post-install` expands `${HOME}` and syncs `~/.jetbrains/acp.json` (`0644`) because JetBrains ACP requires an absolute path.

## Prerequisites & Machine-Specific Notes

1. **Agent Safehouse installed** at `~/.homebrew/bin/safehouse` (this setup uses a user-local Homebrew prefix at `~/.homebrew`).
2. **Junie CLI installed** at `~/.local/bin/junie`.
3. **`LITELLM_MASTER_KEY` exported** in your shell environment (automatically synced into `~/.bash_profile` when installing [`litellm-proxy`](../litellm-proxy/README.md)).

## Quick Start

```bash
# Install ~/bin/junie-safehouse, ~/.config/safehouse/junie-local.sb, and ~/.jetbrains/acp.json
bin/install safehouse

# Verify wrapper, safehouse/junie binaries, ACP config, and LITELLM_MASTER_KEY
bin/doctor safehouse
```

Run Junie directly inside the sandbox from any project directory:

```bash
~/bin/junie-safehouse
```

Or select **junie-safehouse** in your JetBrains IDE's ACP agent settings.

## Files & Manifest

| Repo Source | Target Path | Mode | Purpose |
| --- | --- | --- | --- |
| `safehouse/junie-safehouse` | `~/bin/junie-safehouse` | `0755` | Executable `safehouse` wrapper script invoking `~/.local/bin/junie`. |
| `safehouse/policies/*.sb` | `~/.config/safehouse/junie-local.sb` | `0644` | Scoped Seatbelt policy snippets concatenated by `hooks/post-install` (`desktop-apps.sb`, `docmancer.sb`, `local-tools.sb`). |
| `safehouse/acp.json` | `~/.jetbrains/acp.json` | `0644` | JetBrains ACP template (`${HOME}` expanded by `hooks/post-install`). |
| `safehouse/hooks/post-install` | *(hook)* | `0755` | Compiles `safehouse/policies/*.sb` into `~/.config/safehouse/junie-local.sb` and expands `${HOME}` in `safehouse/acp.json` into `~/.jetbrains/acp.json`. |
| `safehouse/hooks/doctor` | *(hook)* | `0755` | Verifies executables, compiled `junie-local.sb` (SHA-256 and mode), rendered ACP config (SHA-256, mode, JSON command), and `LITELLM_MASTER_KEY`. |
| `safehouse/hooks/_safehouse.py` | *(helper)* | `0644` | Shared `policies/*.sb` compilation, `${HOME}` rendering, atomic write, and SHA-256/mode verification. |

## Health Checks (`bin/doctor safehouse`)

After checking manifest file hashes and permissions, `safehouse/hooks/doctor` verifies:

1. `~/bin/junie-safehouse`, `~/.homebrew/bin/safehouse`, and `~/.local/bin/junie` exist and are executable.
2. `~/.config/safehouse/junie-local.sb` is a regular file (`0644`) whose SHA-256 matches the compiled `safehouse/policies/*.sb` output.
3. `~/.jetbrains/acp.json` is a regular file (`0644`) whose SHA-256 matches `safehouse/acp.json` with `${HOME}` expanded, is valid JSON, defines `agent_servers.junie-safehouse.command`, and points to an executable matching `~/bin/junie-safehouse`.
4. `LITELLM_MASTER_KEY` is set in the current environment (prints a `[WARN]` if unset, since `junie-safehouse` forwards it via `--env-pass=LITELLM_MASTER_KEY`).
