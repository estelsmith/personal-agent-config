# LiteLLM Proxy

This system runs a local Docker Compose [LiteLLM](https://docs.litellm.ai/) gateway on `http://127.0.0.1:4000` with complexity-based model routing (`anthropic-ladder` and `gemini-ladder`), PostgreSQL request and spend logging, a custom Gemini Decisions API adapter sidecar, and Junie-specific request/response callbacks.

## Why I Use It

Sending every agent turn to a flagship reasoning model wastes both money and latency. With `anthropic-ladder` and `gemini-ladder`, the proxy classifies incoming prompts by complexity and routes simple, medium, complex, and reasoning turns to matching effort tiers.

Running a local gateway also lets me smooth over Junie compatibility gaps that upstream LiteLLM doesn't handle out of the box (such as Google's `v1beta/decisions` classifier API, Junie's Google GenAI and capability-filter quirks, and pinning lightweight title/summary side-requests to a fast model). Upstream provider keys stay in `~/litellm-proxy/.env` while agent processes only see a local `LITELLM_MASTER_KEY`, and all spend and prompt logs stay in a local PostgreSQL container.

## How It Fits In

`litellm-proxy` is the model-serving layer of the stack:

- [`safehouse`](../safehouse/README.md) forwards only `LITELLM_MASTER_KEY` into the Junie sandbox (`--env-pass=LITELLM_MASTER_KEY`), keeping real upstream provider API keys outside the agent's sandboxed environment.
- Installing `litellm-proxy` automatically syncs `export LITELLM_MASTER_KEY=...` into `~/.bash_profile` so interactive shells and `junie-safehouse` both pick up the proxy key without manual duplication.

## How It Works

```text
Junie / Client (LITELLM_MASTER_KEY)
   │
   ▼
litellm (127.0.0.1:4000, ghcr.io/berriai/litellm:main-stable)
   ├── custom_callbacks.py
   │     ├── Patches GoogleGenAIGenerateContentHandler for complexity_router
   │     ├── Pins Junie title/summary side-requests to claude-haiku-5-5-low
   │     └── Normalizes capability-filter output & forces named capabilities
   │
   ├── complexity_router (anthropic-ladder / gemini-ladder)
   │     └── gemini-decision-adapter:8080 ──► Gemini Decisions API (v1beta/decisions)
   │
   ├── db (postgres:16-alpine) ──► spend logs & prompt history
   │
   └── Upstream Anthropic / Gemini APIs
```

### Complexity Routing & Models (`config.yaml`)

Requests can target either an individual model/reasoning-effort deployment (`*-low`, `*-medium`, `*-high`) or one of two `auto_router/complexity_router` aliases:

| Alias | `SIMPLE` | `MEDIUM` | `COMPLEX` | `REASONING` | Default |
| --- | --- | --- | --- | --- | --- |
| `anthropic-ladder` | `claude-haiku-5-5-low` | `claude-sonnet-5-5-low` | `claude-sonnet-5-5-medium` | `claude-opus-5-5-low` | `claude-sonnet-5-5-low` |
| `gemini-ladder` | `gemini-4-hydrogen-low` | `gemini-4-hydrogen-low` | `gemini-4-hydrogen-medium` | `gemini-4-hydrogen-high` | `gemini-4-hydrogen-low` |

Both routers classify incoming requests using `gemini-decision-1` (`oss_classifier`, 30s timeout, `heuristic` fallback, 3-message context window, `session_affinity: false`) and escalate when `!LITELLM_ESCALATE` appears.

### Gemini Decisions Sidecar (`gemini_decision_adapter.py`)

Upstream LiteLLM does not natively speak Google's `v1beta/decisions` endpoint for `oss_classifier`. Instead, `config.yaml` points `gemini-decision-1` (`hosted_vllm/gemini-decision-1`) at the local `gemini-decision-adapter` container on port `8080`, which:

- Translates SystemOne/LiteLLM `state`, `images`, and `questions` (`choice`, `score`, `noul` criteria) into Gemini Decisions format.
- Injects `GEMINI_API_KEY` via `x-goog-api-key`.
- Normalizes `total_input_tokens` / `total_output_tokens` back to `input_tokens` / `output_tokens`.
- Exposes `/v1/systemone`, `/v1/decisions`, `/decisions`, and `/health`.

### Junie Compatibility Callbacks (`custom_callbacks.py`)

Loaded via `litellm_settings.callbacks: custom_callbacks.proxy_handler_instance`, this module handles three Junie-specific behaviors:

1. **Google GenAI decision routing**: Monkey-patches `GoogleGenAIGenerateContentHandler.get_structured_messages` so `complexity_router` can inspect Google GenAI `:generateContent` payloads instead of skipping routing. Junie's custom Gemini models must stay on `apiType: "Google"` (`:generateContent`) because LiteLLM's `OpenAICompletion` surface appends `__thought__<base64_signature>` to `tool_call.id` by default, breaking `spawn_subagent` in `/task-dispatcher`.
2. **Side-request pinning**: Intercepts Junie's lightweight title-creator and task-description-summarizer system prompts in `async_pre_call_hook` and routes them straight to `claude-haiku-5-5-low`.
3. **Capability-filter stabilization**: Cleans trailing commentary from Junie capability-filter responses (both streaming and non-streaming) and guarantees any skill/agent explicitly named in the user prompt is included in the returned ID list.

## Prerequisites

- Docker CLI and a running Docker daemon (with `docker compose`).
- API keys for [Anthropic](https://platform.claude.com/settings/keys) (`ANTHROPIC_API_KEY`) and [Google AI Studio](https://aistudio.google.com/api-keys) (`GEMINI_API_KEY`).
- A local proxy master key of your choice (`LITELLM_MASTER_KEY`).

## Quick Start

1. **Install files and start the Compose stack**:
   ```bash
   bin/install litellm-proxy
   ```
   - `litellm-proxy/.env` is gitignored (`sync-or-seed`). If you have a local `litellm-proxy/.env` in the repo, it is synced to `~/litellm-proxy/.env`; otherwise `~/litellm-proxy/.env` is seeded from `.env.example` with mode `0600`.
2. **Populate real secrets** (if `.env` was just seeded from `.env.example`):
   Edit `~/litellm-proxy/.env` and replace the placeholder values for `LITELLM_MASTER_KEY`, `ANTHROPIC_API_KEY`, and `GEMINI_API_KEY`.
3. **Sync `~/.bash_profile` and apply the new `.env` to containers**:
   ```bash
   # Syncs export LITELLM_MASTER_KEY=... into ~/.bash_profile
   bin/install litellm-proxy

   # If containers were already running with placeholder keys, force-recreate them:
   docker compose --project-directory ~/litellm-proxy -f ~/litellm-proxy/docker-compose.yml up -d --force-recreate
   ```
   Then reload your shell so `LITELLM_MASTER_KEY` is exported (also needed by [`safehouse`](../safehouse/README.md)):
   ```bash
   source ~/.bash_profile
   ```
4. **Verify stack and config health**:
   ```bash
   bin/doctor litellm-proxy
   ```

## Files & Manifest

| Repo Source | Target Path | Mode | Sync Mode | Purpose |
| --- | --- | --- | --- | --- |
| `litellm-proxy/docker-compose.yml` | `~/litellm-proxy/docker-compose.yml` | `0644` | `sync` | Defines `litellm`, `gemini-decision-adapter`, and `db` (`postgres:16-alpine`) services. |
| `litellm-proxy/config.yaml` | `~/litellm-proxy/config.yaml` | `0644` | `sync` | Model list, complexity routers, callbacks, and DB logging settings. |
| `litellm-proxy/custom_callbacks.py` | `~/litellm-proxy/custom_callbacks.py` | `0644` | `sync` | Google GenAI patch, Haiku title/summary routing, and capability-filter hook. |
| `litellm-proxy/gemini_decision_adapter.py` | `~/litellm-proxy/gemini_decision_adapter.py` | `0644` | `sync` | Starlette ASGI sidecar translating decisions requests to Gemini API. |
| `litellm-proxy/Dockerfile.adapter` | `~/litellm-proxy/Dockerfile.adapter` | `0644` | `sync` | Container image definition (`python:3.12-slim` + `starlette`, `uvicorn`, `httpx`). |
| `litellm-proxy/.env\|.env.example` | `~/litellm-proxy/.env` | `0600` | `sync-or-seed` | Syncs gitignored `.env` if present in repo; otherwise seeds from `.env.example`. |
| `litellm-proxy/hooks/post-install` | *(hook)* | `0755` | n/a | Syncs `LITELLM_MASTER_KEY` to `~/.bash_profile` and manages Compose lifecycle. |
| `litellm-proxy/hooks/doctor` | *(hook)* | `0755` | n/a | Checks `.env` keys, `~/.bash_profile` sync, Compose container health, and `:4000/health/liveliness`. |

## Hook Behavior & Operations

- **Smart `post-install` restarts**:
  - When manifest files changed (`FILES_CHANGED=1`, e.g., on first install, after editing `config.yaml`, or with `bin/install --force litellm-proxy`), `hooks/post-install` pulls upstream images, builds `gemini-decision-adapter`, stops existing containers (`down`), and brings the stack back up (`up -d --wait`).
  - When no manifest files changed (`FILES_CHANGED=0`), it checks whether all Compose services are running/healthy and `http://127.0.0.1:4000/health/liveliness` responds. If healthy, it skips pulling/rebuilding/restarting; otherwise it runs `up -d --wait`.
- **Inspecting logs or restarting manually**:
  ```bash
  docker compose --project-directory ~/litellm-proxy -f ~/litellm-proxy/docker-compose.yml ps
  docker compose --project-directory ~/litellm-proxy -f ~/litellm-proxy/docker-compose.yml logs -f litellm gemini-decision-adapter
  ```
