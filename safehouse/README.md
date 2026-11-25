# Agent Safehouse Setup for Junie

OS-level sandboxing configuration that wraps the Junie CLI in [Agent Safehouse](https://github.com/eugene1g/agent-safehouse) (`sandbox-exec` on macOS) and exposes it to PhpStorm via ACP.

## Files

| Repo Path | Target Path | Purpose |
| --- | --- | --- |
| `safehouse/junie-safehouse` | `~/bin/junie-safehouse` | Wrapper script executing `~/.local/bin/junie` inside `safehouse` with scoped directory access, Docker support, and `LITELLM_MASTER_KEY` passthrough. |
| `safehouse/junie-local.sb` | `~/.config/safehouse/junie-local.sb` | Machine-local Seatbelt (`.sb`) profile appended via `--append-profile`, granting read access to `~/.homebrew`, `~/npm`, `~/bin`, and `~/.gitignore_global`. |
| `safehouse/acp.json` | `~/.jetbrains/acp.json` | JetBrains / PhpStorm ACP configuration registering the `junie-safehouse` agent server (`--acp=true`). |

## Installation

```bash
install -m 755 safehouse/junie-safehouse ~/bin/junie-safehouse
install -d ~/.config/safehouse ~/.jetbrains
install -m 644 safehouse/junie-local.sb ~/.config/safehouse/junie-local.sb
install -m 644 safehouse/acp.json ~/.jetbrains/acp.json
```

> Note: `acp.json` uses the absolute path `/Users/esmith/bin/junie-safehouse` for `"command"`; update it if your `$HOME` differs.
