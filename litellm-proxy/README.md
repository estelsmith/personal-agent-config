# LiteLLM Proxy

This system runs a local Docker Compose [LiteLLM](https://docs.litellm.ai/) gateway on `http://127.0.0.1:4000` with complexity-based model routing (`anthropic-ladder` and `gemini-ladder`), PostgreSQL request and spend logging, a small Gemini Decisions adapter, and a few Junie compatibility fixes.

## Why I Use It

Sending every agent turn to a flagship reasoning model burns money and latency for no reason. With `anthropic-ladder` and `gemini-ladder`, the proxy classifies incoming prompts by complexity and routes simple, medium, complex, and reasoning turns to matching effort tiers.

Running a local gateway also lets me smooth over Junie compatibility quirks that upstream LiteLLM doesn't handle out of the box (like Google's `v1beta/decisions` classifier API, routing Google `:generateContent` payloads, and pinning Junie's lightweight title/summary side calls to a fast model). Upstream provider keys stay in `~/litellm-proxy/.env` while agent processes only see a local `LITELLM_MASTER_KEY`, and all spend and prompt logs stay in a local Postgres container.

## How It Fits In

- **`safehouse`:** Installing `litellm-proxy` syncs `LITELLM_MASTER_KEY` from `~/litellm-proxy/.env` into `~/.bash_profile`, and [`safehouse`](../safehouse/README.md) forwards only that proxy key into the sandbox. Real Anthropic and Gemini keys never enter Junie's environment.

## How It Works

### Complexity Routing (`config.yaml`)

Requests can target a fixed model/effort tier (`*-low`, `*-medium`, `*-high`) or one of two complexity-routed aliases:

| Alias | `SIMPLE` | `MEDIUM` | `COMPLEX` | `REASONING` | Default |
| --- | --- | --- | --- | --- | --- |
| `anthropic-ladder` | `claude-haiku-5-5-low` | `claude-sonnet-5-5-low` | `claude-sonnet-5-5-medium` | `claude-opus-5-5-low` | `claude-sonnet-5-5-low` |
| `gemini-ladder` | `gemini-4-hydrogen-low` | `gemini-4-hydrogen-low` | `gemini-4-hydrogen-medium` | `gemini-4-hydrogen-high` | `gemini-4-hydrogen-low` |

Both routers classify turns with `gemini-decision-1` (falling back to a heuristic if the classifier times out) and escalate when `!LITELLM_ESCALATE` appears in the prompt.

### Gemini Decisions Sidecar (`gemini_decision_adapter.py`)

LiteLLM doesn't support the Gemini Decisions API yet, so this sidecar translates classifier requests into Gemini Decisions format and injects `GEMINI_API_KEY` so I can keep routing turns by complexity. It's a compatibility layer, specifically.

### Junie Callbacks (`custom_callbacks.py`)

This hooks into LiteLLM to fix three Junie rough edges:

- **Google `:generateContent` routing:** Lets `complexity_router` inspect native Google payloads instead of skipping routing (since Junie's Gemini profiles need `apiType: "Google"` so subagent spawning works).
- **Side-request pinning:** Catches Junie's background title-creator and task-summary prompts and sends them straight to `claude-haiku-5-5-low`.
- **Capability-filter cleanup:** Strips trailing commentary from capability-filter responses and makes sure any skill or agent explicitly named in the user prompt stays in the returned list.

## Prerequisites

- **Docker:** Docker CLI and a running Docker daemon (with `docker compose`).
- **Provider keys:** API keys for [Anthropic](https://platform.claude.com/settings/keys) (`ANTHROPIC_API_KEY`) and [Google AI Studio](https://aistudio.google.com/api-keys) (`GEMINI_API_KEY`).
- **Proxy key:** A local `LITELLM_MASTER_KEY` of your choice.

## Quick Start

1. **Install files and bring up the stack** (on a fresh machine, this seeds `~/litellm-proxy/.env` from `.env.example` unless you already keep a gitignored `litellm-proxy/.env` in the repo):
   ```bash
   bin/install litellm-proxy
   ```
2. **Fill in real keys** (if `.env` was just seeded with placeholders):
   Edit `~/litellm-proxy/.env` and set `LITELLM_MASTER_KEY`, `ANTHROPIC_API_KEY`, and `GEMINI_API_KEY`.
3. **Sync `LITELLM_MASTER_KEY` to `~/.bash_profile` and recreate the containers with the real keys:**
   ```bash
   # Syncs export LITELLM_MASTER_KEY=... into ~/.bash_profile
   bin/install litellm-proxy

   # Recreate containers if they first started with placeholder keys
   docker compose --project-directory ~/litellm-proxy -f ~/litellm-proxy/docker-compose.yml up -d --force-recreate

   # Export LITELLM_MASTER_KEY in your current shell (needed by safehouse too)
   source ~/.bash_profile
   ```
4. **Check stack and proxy health:**
   ```bash
   bin/doctor litellm-proxy
   ```

## Operations & Files

`bin/install litellm-proxy` only pulls, rebuilds, and restarts the Compose stack when config files changed, `--force` was passed, or the proxy isn't healthy. Otherwise it leaves running containers alone.

```bash
# Check container status
docker compose --project-directory ~/litellm-proxy -f ~/litellm-proxy/docker-compose.yml ps

# Tail proxy and adapter logs
docker compose --project-directory ~/litellm-proxy -f ~/litellm-proxy/docker-compose.yml logs -f litellm gemini-decision-adapter
```

| Repo Source | Target Path | What It Is For |
| --- | --- | --- |
| `litellm-proxy/docker-compose.yml` | `~/litellm-proxy/docker-compose.yml` | Defines `litellm`, `gemini-decision-adapter`, and Postgres (`db`). |
| `litellm-proxy/config.yaml` | `~/litellm-proxy/config.yaml` | Model list, complexity routers, callbacks, and DB logging. |
| `litellm-proxy/custom_callbacks.py` | `~/litellm-proxy/custom_callbacks.py` | Google routing patch, Haiku side-request pinning, and capability-filter cleanup. |
| `litellm-proxy/gemini_decision_adapter.py` | `~/litellm-proxy/gemini_decision_adapter.py` | Sidecar translating LiteLLM classifier calls to the Gemini Decisions API. |
| `litellm-proxy/Dockerfile.adapter` | `~/litellm-proxy/Dockerfile.adapter` | Container image for the Gemini Decisions sidecar. |
| `litellm-proxy/.env\|.env.example` | `~/litellm-proxy/.env` | Syncs gitignored `.env` if present; otherwise seeds from `.env.example`. |
| `litellm-proxy/hooks/post-install` | *(hook)* | Syncs `LITELLM_MASTER_KEY` to `~/.bash_profile` and manages Compose restarts. |
| `litellm-proxy/hooks/doctor` | *(hook)* | Checks `.env` keys, `~/.bash_profile`, containers, and `:4000/health/liveliness`. |
