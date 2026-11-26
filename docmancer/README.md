# Global Docmancer Setup

Global configuration, Mise environment injection, and Junie skill for [Docmancer](https://docmancer.dev/docs).

## Files

| Repo Path | Target Path | Purpose |
| --- | --- | --- |
| `docmancer/docmancer.yaml` | `~/.docmancer/docmancer.yaml` | Global SQLite + `sqlite-vec` + Ollama OpenAI-compatible embeddings (`embeddinggemma-2:740m`) configuration. |
| `docmancer/mise-env.toml` | `~/.config/mise/conf.d/docmancer.toml` | Injects `OPENAI_BASE_URL` and `OPENAI_API_KEY` into Mise's global environment for local Ollama embeddings. |
| `docmancer/skills/docmancer/SKILL.md` | `~/.junie/skills/docmancer/SKILL.md` | Global Junie skill instructing agents to query and index docs via `mise exec -- docmancer`. |
| `docmancer/hooks/doctor` | Health check hook | Verifies `~/bin/mise`, `OPENAI_BASE_URL`/`OPENAI_API_KEY` in `mise env --json`, `mise exec -- docmancer --version`, and the `embeddings-openai` extra (`openai`). |

## Usage

```bash
bin/install mise docmancer
bin/doctor mise docmancer
```
