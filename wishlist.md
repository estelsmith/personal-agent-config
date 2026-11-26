# Wishlist

Random things I want to be consolidated/fixed in my personal agent configuration.

## Items

- Stable LiteLLM session IDs for each Junie ACP session?
  - Currently each turn gets a new session, and it's annoying to see which chats belong to which session.
  - Requires using Junie to inspect logs to correlate what's what. Not very human-friendly.
- How can we remove the system `python` dependency from the `doctor`/`install` commands?
    - Maybe pure bash?
    - Maybe bootstrap Mise before anything else with Python as the only pre-installed tool?
- Why `python3` instead of `python` in CLI? Both are in Mise, so maybe switch to `python` so it always uses the current version.
- The CLI tooling for `doctor`/`install` is pretty garbage. It needs to be rewritten to be more coherent.
  - This is what you get for blindly vibe-coding a CLI tool without quality enforcement. LLMs can reason about this shit but humans can't.
- System installations run in arbitrary order, when in reality the `mise` system needs to be the very first. Without Mise, most of this will fall apart.
  - Implement a simple DAG that ensures that `doctor mise` comes back clean before anything the depends on it for doctor/install.
  - Don't automatically `install mise` when trying to install dependents. Simply don't allow the dependency to continue to installation if this prerequisite fails.
- `litellm-proxy` system install exposes the raw `docker compose` ouputs, which streams hundred of lines when downloading/building images.
  - I don't need to see the raw output. Just a summary of what steps are happening. Such as if `litellm-proxy` image downloads, note that a new image was downloaded. Or if a build actually took place, then note that.
- `safehouse` is not being installed/managed by this repo. It's expected to already exist.
  - Verify this is true. I'm pretty sure it is.
- I want to get rid of homebrew completely in exchange for Mise.
  - The only hard requirement for my agent config is that Mise be installed. May create a simple `bootstrap.sh` that downloads/installs the latest version to get things going.
- `litellm-proxy` requires setting `.env` inside of it, and also seeds from `.env.example`.
  - Move `.env` out of `litellm-proxy` to `/litellm-proxy.env`. Require the file exist and contain all env vars.
  - Remove "seed" functionality all-together. It will result in a broken LiteLLM config anyway.
- Ollama. Can be managed by Mise, and `doctor`/`install` can ensure the `embeddinggemma-2:740m` is installed for docmancer's use.
  - Currently installed/configured globally, completely disconnected from the agent config repo.
- `junie` or `litellm-proxy` should manage Junie custom models for LiteLLM in `~/.junie/models`
- Can `junie` install Junie itself? Probably.
- https://github.com/Graphify-Labs/graphify for codebase knowledge? Or maybe chunkhound, or something similar?
- Install and manage https://github.com/estelsmith/llm-task-dispatcher
  - Probably can go in `junie` since it's junie-specific.
  - Shallow clone of repo, run install/doctor commands internally?
- Move steel browser into this repo. See `~/repositories/firmprospects/engage/` for example setup.
- Can we move away from custom `doctor`/`install` commands to Mise tasks, or a more generic config management system?
  - Ansible, etc.
- [hk](https://hk.jdx.dev/) for global/local git hook management
  - Useful for Graphify automatic graph updates on git checkout, update, or pre-commit.
- `safehouse` currently allows Docker CLI tools (`Docker.app/Contents/Resources/{bin,cli-plugins}`) and broad Docker daemon access via `--enable=docker`. Implement a host-level Docker socket proxy so Junie can only work with the project-local Docker Compose setup and cannot abuse unrestricted Docker socket access (such as mounting host paths or escalating to root).
