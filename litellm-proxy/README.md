# LiteLLM Proxy Setup for Junie

Local [LiteLLM Proxy](https://docs.litellm.ai/) Docker Compose stack exposing complexity-routed model ladders (`anthropic-ladder` and `gemini-ladder`) on `127.0.0.1:4000`, backed by PostgreSQL, a Gemini Decisions API adapter, and Junie-specific compatibility callbacks.

## Files

| Repo Path | Target Path | Purpose |
| --- | --- | --- |
| `litellm-proxy/docker-compose.yml` | `~/litellm-proxy/docker-compose.yml` | Compose stack defining `litellm` (`127.0.0.1:4000`), `gemini-decision-adapter`, and `db` (`postgres:16-alpine` with `litellm-db` volume). |
| `litellm-proxy/config.yaml` | `~/litellm-proxy/config.yaml` | Defines `gemini-4-hydrogen` and `claude-*-5-5` effort tiers, `anthropic-ladder` / `gemini-ladder` complexity routers, and `gemini-decision-1`. |
| `litellm-proxy/custom_callbacks.py` | `~/litellm-proxy/custom_callbacks.py` | Patches `GoogleGenAIGenerateContentHandler.get_structured_messages` for GenAI routing, pins Junie title/summary side-requests to `claude-haiku-5-5-low`, and stabilizes Junie capability-filter responses. |
| `litellm-proxy/gemini_decision_adapter.py` | `~/litellm-proxy/gemini_decision_adapter.py` | Compatibility layer (Starlette ASGI sidecar) translating the unsupported Gemini Decisions API (`v1beta/decisions`) into the LiteLLM-supported `hosted_vllm` decisions API (`/v1/systemone`, `/v1/decisions`, `/decisions`), since LiteLLM does not natively support the Gemini Decisions API yet. |
| `litellm-proxy/Dockerfile.adapter` | `~/litellm-proxy/Dockerfile.adapter` | Python 3.12 image (`starlette`, `uvicorn`, `httpx`) for running `gemini-decision-adapter` on port `8080`. |
| `litellm-proxy/.env.example` | `~/litellm-proxy/.env.example` | Template `.env` file containing the required proxy master key and provider API keys. |

## Installation

1. Copy the configuration and service files into `~/litellm-proxy`:

```bash
install -d ~/litellm-proxy
install -m 644 \
  litellm-proxy/docker-compose.yml \
  litellm-proxy/config.yaml \
  litellm-proxy/custom_callbacks.py \
  litellm-proxy/gemini_decision_adapter.py \
  litellm-proxy/Dockerfile.adapter \
  ~/litellm-proxy/
```

2. Copy `litellm-proxy/.env.example` to `~/litellm-proxy/.env` and fill in the required keys:

```bash
install -m 600 litellm-proxy/.env.example ~/litellm-proxy/.env
```

```dotenv
LITELLM_MASTER_KEY=sk-local-change-me
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
```

3. Build and start the stack:

```bash
cd ~/litellm-proxy
docker compose up -d --build
```

> Note: `LITELLM_MASTER_KEY` in `~/litellm-proxy/.env` should match the `LITELLM_MASTER_KEY` exported in your shell environment when running Junie (including through `safehouse/junie-safehouse`, which passes it into the sandbox).
