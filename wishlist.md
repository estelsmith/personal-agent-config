# Wishlist

Random things I want to be consolidated into my personal agent configuration.

## Items

- Ollama. Can be managed by Mise, and `doctor`/`install` can ensure the `embeddinggemma-2:740m` is installed for docmancer's use.
  - Currently installed/configured globally, completely disconnected from the agent config repo.
- `junie` or `litellm-proxy` should manage Junie custom models for LiteLLM in `~/.junie/models`
- Can `junie` install Junie itself? Probably.
- https://github.com/Graphify-Labs/graphify for codebase knowledge? Or maybe chunkhound, or something similar?
- Install and manage https://github.com/estelsmith/llm-task-dispatcher
  - Probably can go in `junie` since it's junie-specific.
  - Shallow clone of repo, run install/doctor commands internally?
