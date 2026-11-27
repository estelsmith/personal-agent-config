# Mise

This system installs [Mise](https://mise.jdx.dev/) (`~/bin/mise`), hooks bash activation into `~/.bash_profile`, and keeps my global CLI runtimes (`python`, `uv`, and `pipx:docmancer`) pinned in `mise/tools.toml`.

## Why I Use It

I want one place to declare the Python runtime and CLI tools my setup relies on, rather than dealing with macOS system Python drift, Homebrew upgrades shifting paths underneath me, or random global `pip` installs.

Using `mise exec -- <tool>` also keeps runs consistent everywhere. Interactive terminals, JetBrains IDE subshells, and sandboxed sessions all get the same pinned binaries and `conf.d` environment variables even when `~/.bash_profile` wasn't sourced.

## How It Fits In

- **`docmancer`:** [`docmancer`](../docmancer/README.md) relies on Mise to install `pipx:docmancer` (with its OpenAI embeddings and SOCKS extras) and inject local Ollama environment variables whenever `mise exec -- docmancer` runs.
- **`safehouse`:** [`safehouse`](../safehouse/README.md) opens up `~/bin` inside the sandbox so Junie can call `mise` and Mise-managed tools directly.

## How It Works

Unlike manifest-based systems, `mise/` doesn't have a `manifest` file. Instead, `bin/install mise` does three things from `mise/tools.toml`:

1. **Downloads `~/bin/mise`:** Grabs the latest Mise binary from GitHub if `~/bin/mise` is missing or broken.
2. **Wires bash activation:** Adds `eval "$(mise activate bash)"` to `~/.bash_profile` (ahead of `direnv` if present so Mise tools win on `PATH`).
3. **Syncs global tools:** Runs `mise use --global` for every entry in `mise/tools.toml`. If a tool's `extras` or `with` packages change without a version bump, the hook forces a reinstall so those dependencies actually get picked up.

## Prerequisites

- **OS:** macOS or Linux (`arm64` or `x64`).
- **Network:** Access to GitHub releases for the first bootstrap.
- **Shell `PATH`:** `~/bin` on `PATH` for interactive shells.

## Quick Start

```bash
# Install ~/bin/mise, update ~/.bash_profile, and install global tools
bin/install mise

# Check the binary, bash activation, and installed tool versions
bin/doctor mise

# Reload your shell after the first install
source ~/.bash_profile
```

## Updating Tools & Overrides

- **Add or bump a tool:** Edit `mise/tools.toml`, then run `bin/install mise` and `bin/doctor mise`.
- **Pin a specific Mise release:** Set `MISE_RELEASE_TAG` (like `v2026.11.14`) or `MISE_DOWNLOAD_URL` before running `bin/install mise` if you don't want the latest release.
- **See what Mise has installed globally:**
  ```bash
  ~/bin/mise ls --global
  ```

## Files

| Path | What It Is For |
| --- | --- |
| `mise/tools.toml` | Pinned global tool versions and `pipx` extras/dependencies. |
| `mise/hooks/post-install` | Bootstraps `~/bin/mise`, updates `~/.bash_profile`, and syncs `mise/tools.toml`. |
| `mise/hooks/doctor` | Checks `~/bin/mise`, bash activation, and global tool status. |
