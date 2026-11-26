# Wishlist

Random things I want to be consolidated/fixed in my personal agent configuration.

## Items

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
- How can we remove the system `python` dependency from the `doctor`/`install` commands?
  - Maybe pure bash?
- Move steel browser into this repo. See `~/repositories/firmprospects/engage/` for example setup.
- Can we move away from custom `doctor`/`install` commands to Mise tasks, or a more generic config management system?
  - Ansible, etc.
