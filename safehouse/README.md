# Safehouse

This system wraps Junie CLI sessions on macOS in `sandbox-exec` via [Agent Safehouse](https://agent-safehouse.dev/). It installs `~/bin/junie-safehouse`, compiles my local Seatbelt overrides into `~/.config/safehouse/junie-local.sb`, and registers the wrapper in `~/.jetbrains/acp.json` so terminal runs and JetBrains IDEs launch Junie inside the same sandbox.

## Why I Use It

Autonomous coding agents run shell commands and edit files, so I don't want them having free rein over the rest of my machine. Sandboxing restricts writes to the active project and explicit agent directories while blocking access to unrelated repos, browser profiles, SSH keys, and host secrets.

Pointing both my terminal workflow and JetBrains IDE's `~/.jetbrains/acp.json` at `~/bin/junie-safehouse` means Junie gets the exact same boundaries no matter where I launch it.

## How It Fits In

- **`junie` & `docmancer`:** Gives Junie read/write access to `~/.junie` (rules, skills, sessions) and `~/.docmancer` (local doc index), plus read access to `~/bin` and `~/.homebrew` so agents can run `mise exec -- docmancer` and other [`mise`](../mise/README.md)-managed tools.
- **`litellm-proxy`:** Forwards only `LITELLM_MASTER_KEY` into the sandbox so Junie talks to [`litellm-proxy`](../litellm-proxy/README.md) without ever seeing `ANTHROPIC_API_KEY` or `GEMINI_API_KEY`.

## How It Works

- **Wrapper (`~/bin/junie-safehouse`):** Launches `~/.local/bin/junie` through `~/.homebrew/bin/safehouse` with all CLI flags forwarded (including `--acp=true`), Docker access enabled, read/write access to `~/.junie` and `~/.mcp-auth`, read-only access to Junie/PhpStorm/MCP tool directories, and `LITELLM_MASTER_KEY` passed from the host environment.
- **Seatbelt policies (`safehouse/policies/*.sb`):** `bin/install safehouse` stitches these files alphabetically into `~/.config/safehouse/junie-local.sb`:
  - **`desktop-apps.sb`:** Blocks launching macOS `.app` bundles, `open`, and `osascript` (with narrow carve-outs for Docker CLI tools and PhpStorm's headless MCP server).
  - **`docmancer.sb`:** Allows read/write access to `~/.docmancer`.
  - **`local-tools.sb`:** Allows read access to `~/.homebrew`, `~/npm`, `~/bin`, and `~/.gitignore_global`.
- **JetBrains ACP (`~/.jetbrains/acp.json`):** Registers `junie-safehouse` with `--acp=true`, expanding `${HOME}` on install because JetBrains ACP requires an absolute path.

## Prerequisites

- **Agent Safehouse:** Installed at `~/.homebrew/bin/safehouse` (this setup uses a user-local Homebrew prefix at `~/.homebrew`).
- **Junie CLI:** Installed at `~/.local/bin/junie`.
- **Proxy key:** `LITELLM_MASTER_KEY` exported in your shell (handled by `bin/install litellm-proxy`).

## Quick Start

```bash
# Install ~/bin/junie-safehouse, ~/.config/safehouse/junie-local.sb, and ~/.jetbrains/acp.json
bin/install safehouse

# Check binaries, compiled policy, ACP config, and LITELLM_MASTER_KEY
bin/doctor safehouse

# Launch Junie inside the sandbox from any project directory
~/bin/junie-safehouse
```

Or pick **junie-safehouse** in your JetBrains IDE's ACP agent settings.

## Files

| Repo Source | Target Path | What It Is For |
| --- | --- | --- |
| `safehouse/junie-safehouse` | `~/bin/junie-safehouse` | Safehouse wrapper script launching `~/.local/bin/junie`. |
| `safehouse/policies/*.sb` | `~/.config/safehouse/junie-local.sb` | Seatbelt overrides (`desktop-apps.sb`, `docmancer.sb`, `local-tools.sb`). |
| `safehouse/acp.json` | `~/.jetbrains/acp.json` | JetBrains ACP agent registration (`${HOME}` expanded on install). |
| `safehouse/hooks/post-install` | *(hook)* | Compiles `policies/*.sb` and writes `~/.jetbrains/acp.json`. |
| `safehouse/hooks/doctor` | *(hook)* | Verifies binaries, compiled policy, ACP JSON, and `LITELLM_MASTER_KEY`. |
