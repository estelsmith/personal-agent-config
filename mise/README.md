# Mise

This system installs [Mise](https://mise.jdx.dev/) (`~/bin/mise`), wires bash shell activation into `~/.bash_profile`, and keeps my global runtimes (`python`, `uv`, and `pipx:docmancer`) pinned to the versions in `mise/tools.toml`.

## Why I Use It

I want one declarative source of truth for the Python runtime and CLI utilities my agent setup depends on, instead of dealing with system Python drift, Homebrew Python upgrades, or ad-hoc global `pip` installs.

Using `mise exec -- <tool>` also makes runs consistent everywhere: interactive terminals, JetBrains IDE subshells, and sandboxed sessions all get the same pinned binaries and `conf.d` environment variables even when `~/.bash_profile` hasn't been sourced.

## How It Fits In

`mise` serves as the runtime foundation for the other systems in this repository:

- [`docmancer`](../docmancer/README.md) relies on Mise both to install `pipx:docmancer` (with its `embeddings-openai` and `pysocks` dependencies) and to inject local Ollama environment variables from `~/.config/mise/conf.d/docmancer.toml` whenever `mise exec -- docmancer` runs.
- [`safehouse`](../safehouse/README.md) exposes `~/bin` inside the Junie sandbox so sandboxed agents can run `~/bin/mise` and Mise-managed tools directly.

## How It Works

Unlike manifest-based systems, `mise/` doesn't use a `manifest` file. Instead, `mise/hooks/post-install` and `mise/hooks/doctor` read `mise/tools.toml` and converge the machine in three steps:

1. **Binary bootstrap (`~/bin/mise`)**: Checks whether `~/bin/mise` exists and responds to `--version`. If missing, it detects the OS (`macos` or `linux`) and architecture (`arm64` or `x64`), resolves the latest release from `jdx/mise` on GitHub, downloads it atomically, and sets mode `0755`.
2. **Shell activation (`~/.bash_profile`)**: Ensures `eval "$(mise activate bash)"` is present in `~/.bash_profile` (inserted before `eval "$(direnv hook bash)"` if present so Mise tools sit ahead of direnv on `PATH`).
3. **Global tools sync (`~/.config/mise/config.toml`)**: Runs `mise use --global` for every entry in `mise/tools.toml`:
   - `python = "3.15"`
   - `uv = "0.13.10"`
   - `"pipx:docmancer" = { version = "0.9.17", extras = ["embeddings-openai"], with = ["pysocks"] }`

   If a tool's target version is already on disk but its options changed (for example, adding `extras` or `with` packages to `pipx:docmancer`), `post-install` automatically runs `mise install --force` so the extra packages actually get installed into that environment.

## Prerequisites

- macOS or Linux (`arm64` or `x64`).
- Network access to GitHub releases (`curl` or Python `urllib`) for the initial bootstrap.
- `~/bin` on your `PATH` for interactive shells.

## Quick Start

```bash
# Install ~/bin/mise, update ~/.bash_profile, and install global tools
bin/install mise

# Verify binary, bash activation, config.toml, and installed tool versions
bin/doctor mise
```

Reload your shell profile (or open a new terminal) after the first install:

```bash
source ~/.bash_profile
```

## Files & Hooks

| Path | Role | Details |
| --- | --- | --- |
| `mise/tools.toml` | Source of truth | `[tools]` table defining global versions and `pipx` extras/dependencies. |
| `mise/hooks/post-install` | Install and sync hook | Bootstraps `~/bin/mise`, updates `~/.bash_profile`, and runs `mise use --global` (plus `mise install --force` when options change). |
| `mise/hooks/doctor` | Health check hook | Verifies `~/bin/mise --version`, active `mise activate bash` in `~/.bash_profile`, exact tool specs in `~/.config/mise/config.toml`, and `mise ls --global --json` install status. |
| `mise/hooks/_mise.py` | Shared helper module | TOML parsing, GitHub release download, atomic `~/.bash_profile` editing, and Mise CLI wrappers. |

## Updating Tools & Overrides

- **Add or bump a tool**: Edit `mise/tools.toml`, then run `bin/install mise` and `bin/doctor mise`.
- **Override the Mise release download** (optional): Set `MISE_RELEASE_TAG` (e.g., `v2026.11.14`) or `MISE_DOWNLOAD_URL` in the environment before running `bin/install mise`.
- **Check what Mise sees globally**:
  ```bash
  ~/bin/mise ls --global
  ```
