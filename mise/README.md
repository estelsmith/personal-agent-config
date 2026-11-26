# Global Mise Setup

Installs and verifies [Mise](https://mise.jdx.dev/) and global developer/agent runtimes (`python`, `uv`, and `pipx:docmancer`).

## Files & Hooks

| Path | Target / Action | Purpose |
| --- | --- | --- |
| `mise/tools.toml` | Applied via `mise use --global` | Declares global tools (`python`, `uv`, `pipx:docmancer`) written into `~/.config/mise/config.toml`. |
| `mise/hooks/post-install` | Lifecycle hook | Downloads `~/bin/mise` from [GitHub releases](https://github.com/jdx/mise/releases) if missing, adds `eval "$(mise activate bash)"` to `~/.bash_profile`, and runs `mise use --global` for `mise/tools.toml`. |
| `mise/hooks/doctor` | Health check hook | Verifies `~/bin/mise` is executable, `~/.bash_profile` activates Mise, and all global tools in `mise/tools.toml` are configured and installed. |

## Usage

```bash
bin/install mise
bin/doctor mise
```
