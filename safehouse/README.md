# Safehouse Setup

Sandboxes Junie CLI sessions on macOS using [Agent Safehouse](https://agent-safehouse.dev/) (`sandbox-exec`). Installs a wrapper script (`~/bin/junie-safehouse`), a machine-local Seatbelt profile (`~/.config/safehouse/junie-local.sb`), and a JetBrains ACP server configuration (`~/.jetbrains/acp.json`) so both terminal sessions and JetBrains IDEs launch Junie inside a tight filesystem/environment sandbox.

## What It's For & Why We Use It

- **What it is for**: Provides a drop-in sandboxed launcher (`junie-safehouse`) for running Junie from the terminal or inside JetBrains IDEs via ACP.
- **Why we use it**:
  - **Least-privilege isolation**: Autonomous coding agents execute shell commands and edit files; sandboxing restricts writes to the active project and explicit agent state directories while blocking access to unrelated projects, browser data, SSH keys, and host secrets.
  - **Consistent policy across CLI & IDE**: Using the same wrapper script in both terminal runs and `~/.jetbrains/acp.json` guarantees identical sandbox boundaries everywhere Junie runs.

## How It Fits Into the Agent Config

`safehouse` is the execution boundary that ties the other systems together safely at runtime:

- **[`junie`](../junie/README.md) & [`docmancer`](../docmancer/README.md)**: Grants read/write access to `~/.junie` (global `AGENTS.md`, skills, sessions) and `~/.docmancer` (local documentation index and embeddings), while allowing read access to `~/bin` and `~/.homebrew` so agents can run `mise exec -- docmancer` and [`mise`](../mise/README.md)-managed tools.
- **[`litellm-proxy`](../litellm-proxy/README.md)**: Passes `LITELLM_MASTER_KEY` into the sandbox (`--env-pass=LITELLM_MASTER_KEY`) so Junie talks to the local proxy without ever seeing `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` in its environment.

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
- **Appended Seatbelt profile (`junie-local.sb` → `~/.config/safehouse/junie-local.sb`)**:
  - Allows metadata & read access to `~/.homebrew`, `~/npm`, `~/bin`, and `~/.gitignore_global`.
  - Allows read/write access to `~/.docmancer` (SQLite index, `sqlite-vec` database, extracted docs, and embeddings cache).
- **JetBrains ACP registration (`acp.json` → `~/.jetbrains/acp.json`)**:
  - Registers the `junie-safehouse` agent server with `--acp=true` for JetBrains IDEs.

## Prerequisites & Machine-Specific Notes

1. **Agent Safehouse installed** at `~/.homebrew/bin/safehouse` (this setup uses a user-local Homebrew prefix at `~/.homebrew`).
2. **Junie CLI installed** at `~/.local/bin/junie`.
3. **`LITELLM_MASTER_KEY` exported** in your shell environment (automatically synced into `~/.bash_profile` when installing [`litellm-proxy`](../litellm-proxy/README.md)).
4. **Username path in `acp.json`**: `safehouse/acp.json` sets `"command": "/Users/esmith/bin/junie-safehouse"` because JetBrains ACP requires an absolute path. If adapting this repo for a different macOS user, update that path to match `/Users/<you>/bin/junie-safehouse`.

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
| `safehouse/junie-local.sb` | `~/.config/safehouse/junie-local.sb` | `0644` | Appended Seatbelt rules for `~/.homebrew`, `~/npm`, `~/bin`, `~/.gitignore_global`, and `~/.docmancer`. |
| `safehouse/acp.json` | `~/.jetbrains/acp.json` | `0644` | JetBrains ACP server definition pointing to `junie-safehouse --acp=true`. |
| `safehouse/hooks/doctor` | *(hook)* | `0755` | Verifies executables, ACP JSON command path, and `LITELLM_MASTER_KEY`. |

## Health Checks (`bin/doctor safehouse`)

After checking manifest file hashes and permissions, `safehouse/hooks/doctor` verifies:

1. `~/bin/junie-safehouse`, `~/.homebrew/bin/safehouse`, and `~/.local/bin/junie` exist and are executable.
2. `~/.jetbrains/acp.json` is valid JSON, defines `agent_servers.junie-safehouse.command`, and points to an executable matching `~/bin/junie-safehouse`.
3. `LITELLM_MASTER_KEY` is set in the current environment (prints a `[WARN]` if unset, since `junie-safehouse` forwards it via `--env-pass=LITELLM_MASTER_KEY`).
