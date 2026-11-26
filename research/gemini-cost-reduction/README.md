# Gemini Cost Reduction Analysis

Evaluation of cost-reduction recommendations from [`gemini_chat_transcript.md`](./gemini_chat_transcript.md) (Gemini Desktop chat transcript from 2026-11-26) against the current `personal-agent-config` setup, the running `litellm-proxy` container (`litellm` `1.111.0`), and observed local Postgres usage telemetry (`LiteLLM_SpendLogs`).

> **Source Attribution:** All original cost-reduction ideas, pricing assumptions, subscription comparisons, and workflow context evaluated in this document come from [`gemini_chat_transcript.md`](./gemini_chat_transcript.md).

## Actionable Improvements Summary

| Priority | Actionable Improvement | Target Files / Components | Expected Impact | Status / Caveats |
| :--- | :--- | :--- | :--- | :--- |
| **High** | Propagate `reasoning_effort` to `:generateContent` (`generationConfig.thinkingConfig`) or switch `gemini-ladder` to `apiType: "OpenAICompletion"` | `litellm-proxy/custom_callbacks.py`, `litellm-proxy/config.yaml`, `~/.junie/models/gemini-ladder.json` | Directly cuts thinking tokens (currently **72% to 86%** of Hydrogen output tokens; output is **32% to 37%** of spend) on `low` and `medium` tiers | **Config bug found:** `apiType: "Google"` ignores `litellm_params.reasoning_effort` in LiteLLM `1.111.0` |
| **High** | Work in focused bursts on 1 to 2 active repos at a time to preserve the ~5-minute implicit cache TTL | Operator workflow across concurrent Junie sessions | Protects the 95% cache discount (`$0.075/1M` vs `$1.50/1M`); uncached input (~12.7% of prompt tokens on Nov 26) drives **~47% of daily spend** (`$12.26/day`) | Ready immediately; no code changes required |
| **Medium** | Add global guidance to batch parallel file reads/searches and delegate noisy codebase exploration to subagents returning lean summaries | `junie/rules/*.md` (compiles to `~/.junie/AGENTS.md`), `~/.junie/agents/*.md` | Reduces full-prefix re-sends per discovery loop and keeps main-session context smaller across turns | Put rules in `junie/rules/*.md` and run `bin/install junie` (do not use `.junie/guidelines.md` or edit `~/.junie/AGENTS.md` directly) |
| **Medium** | Reconcile `task-dispatcher-planning.md` reasoning level (`high`) with its target deployment (`gemini-4-hydrogen-medium`) | `~/.junie/agents/task-dispatcher-planning.md` | Avoids unintended mismatch once `reasoning_effort` propagation is fixed | Minor config cleanup; note custom subagents use frontmatter `model`, not `subagentsMode: "Auto"` |
| **Optional** | Add a separate Flex profile (`service_tier: "flex"`, 50% discount) with Standard fallback for non-blocking background runs or `task-dispatcher-verification.md` | `litellm-proxy/config.yaml`, `litellm-proxy/custom_callbacks.py`, dedicated `~/.junie/models/*.json` | **50% off** input/output/cached rates (`$0.75` / `$3.75` / `$0.0375` per 1M) for async work | **Blocked on current stack:** 1 to 15 min latency + capacity shedding makes Flex unusable for interactive coding; LiteLLM `1.111.0` `google_genai` also drops `service_tier` (requires `OpenAICompletion`, LiteLLM `1.112.0+`, or `serviceTier` injection) |
| **Optional** | Trial `gemini/gemini-4-neon` (`$3.00` / `$15.00` per 1M) selectively on `task-dispatcher-planning.md` | `litellm-proxy/config.yaml`, `~/.junie/agents/task-dispatcher-planning.md` | Potentially fewer downstream retry loops on complex multi-file tasks | Planning deployment is **$15.66** (~13.6% of Hydrogen spend); only saves net cost if better plans reduce `gemini-ladder` retries |
| **Low** | Enable `session_affinity: true` or prompt-level routing pins on `complexity_router` | `litellm-proxy/config.yaml` | Shaves ~0.4 to 1.0s decision-sidecar latency per tool turn | Negligible token savings (`gemini-decision-1` is only **~$1.57 total** across 2,690 logged calls) |
| **No Action** | Keep `classifier_context_window_size: 3`, `claude-haiku-5-5-low` side-request routing, `safehouse` key isolation, and deterministic `AGENTS.md` rules; skip `gemini-3.8-flash`, OAuth bridges, and AI Studio free tier | `litellm-proxy/`, `safehouse/`, `junie/` | Already optimal or ruled out by security/ToS/quota/model constraints | Verified in repo config, `LiteLLM_SpendLogs`, and `gemini_chat_transcript.md` |

## Context & Pricing Baseline (from `gemini_chat_transcript.md`)

- **Workload profile:** Heavy daily usage across **4 to 5 concurrent Junie agent sessions** on different repositories, roughly **$20 to $40/day** in API spend, with an explicit **"Gemini 4 only"** preference (ruling out `gemini-3.8-flash`).
- **Model rates & caching rules cited in `gemini_chat_transcript.md`:**
  - `gemini-4-hydrogen` (Standard): **$1.50/1M** input, **$0.075/1M** cached input (**95% discount**, implicit caching only, minimum 4,096 tokens, ~5-minute TTL, zero storage fees), **$7.50/1M** output (including thinking tokens). Supports four reasoning levels (`low`, `medium`, `high`, `xhigh`, defaulting to `high`).
  - `gemini-4-hydrogen` (Flex): **$0.75/1M** input, **$0.0375/1M** cached input, **$3.75/1M** output (**50% discount**), with a **1 to 15 minute** target latency, 600+ second recommended client timeouts, and sheddable capacity (`503`/`429` fallbacks).
  - `gemini-4-neon` (Standard): **$3.00/1M** input, **$0.150/1M** cached input, **$15.00/1M** output (**2x Hydrogen**; Flex at `$1.50` / `$7.50`).
  - `gemini-decision-1` (`/v1beta/decisions`): **$0.10/1M** input, **$0** output, **no context caching**. AI Studio free tier cap is `200 RPM / 50,000 TPM / 10,000 RPD`.
  - Consumer **Google AI Plus** / **Pro** (`$19.99/mo`) / **Ultra** (`$99.99 to $199.99/mo`) plans cover Gemini Desktop and Antigravity only (not API key traffic). Since November 13, 2026, Pro/Neon models in Gemini Desktop and Antigravity are gated to Pro+.

## Current Setup Snapshot

### 1. LiteLLM Proxy (`litellm-proxy/`)

- **`litellm-proxy/config.yaml`**:
  - Defines three `gemini/gemini-4-hydrogen` deployments (`gemini-4-hydrogen-low`, `gemini-4-hydrogen-medium`, `gemini-4-hydrogen-high`), setting `reasoning_effort` (`low`, `medium`, `high`) and `reasoning_effort_levels`.
  - Defines `anthropic/claude-haiku-5-5`, `anthropic/claude-sonnet-5-5`, and `anthropic/claude-opus-5-5` across `low`, `medium`, and `high`.
  - Defines `gemini-decision-1` (`hosted_vllm/gemini-decision-1`) pointing at the local `http://gemini-decision-adapter:8080` sidecar (`mode: decisions`, `max_input_tokens: 262144`).
  - Defines two `auto_router/complexity_router` aliases:
    - `anthropic-ladder`: `SIMPLE` -> `claude-haiku-5-5-low`, `MEDIUM` -> `claude-sonnet-5-5-low`, `COMPLEX` -> `claude-sonnet-5-5-medium`, `REASONING` -> `claude-opus-5-5-low`, default `claude-sonnet-5-5-low`.
    - `gemini-ladder`: `SIMPLE` -> `gemini-4-hydrogen-low`, `MEDIUM` -> `gemini-4-hydrogen-low`, `COMPLEX` -> `gemini-4-hydrogen-medium`, `REASONING` -> `gemini-4-hydrogen-high`, default `gemini-4-hydrogen-low`.
    - Both routers use `classifier_type: oss_classifier` (`gemini-decision-1`, `timeout_ms: 30000`, `classifier_fallback: heuristic`, `classifier_context_window_size: 3`, `escalation_keywords: [ "!LITELLM_ESCALATE" ]`, `session_affinity: false`).
  - `litellm_settings.drop_params: true`, `callbacks: custom_callbacks.proxy_handler_instance`.
- **`litellm-proxy/custom_callbacks.py`**:
  - Monkey-patches `GoogleGenAIGenerateContentHandler.get_structured_messages` so `complexity_router` inspects `:generateContent` payloads instead of skipping routing.
  - Intercepts Junie side-requests (`"You are a chat response title creator"`, `"You are a programming task description summarizer"`) in `async_pre_call_hook` and pins them to `claude-haiku-5-5-low` (handling both OpenAI/Anthropic `messages` and Google GenAI `systemInstruction`).
  - Normalizes Junie capability-filter (`"You are a capability filter agent"`) outputs in `async_post_call_success_hook` and `async_post_call_streaming_iterator_hook` so small/fast models do not drop explicitly named skills/agents.
- **`litellm-proxy/gemini_decision_adapter.py`**:
  - Translates LiteLLM SystemOne/decisions payloads to `https://generativelanguage.googleapis.com/v1beta/decisions` using `GEMINI_API_KEY`.
- **`safehouse/junie-safehouse` & `litellm-proxy/hooks/post-install`**:
  - Isolates `GEMINI_API_KEY` inside `~/litellm-proxy/.env`; `safehouse/junie-safehouse` forwards only `LITELLM_MASTER_KEY` via `--env-pass` to sandboxed Junie sessions.

### 2. Junie Configuration (`~/.junie/` and `junie/`)

- **`~/.junie/models/gemini-ladder.json`** (and `litellm-gemini-4-hydrogen-{low,medium,high}.json`):
  - `primaryModel`: `gemini-ladder` via `apiType: "Google"` (`http://localhost:4000/v1beta/models/gemini-ladder:generateContent`).
  - `fasterModel`: `claude-haiku-5-5-low` via `apiType: "OpenAICompletion"` (`http://localhost:4000/v1/chat/completions`).
- **`~/.junie/settings.json`**:
  - `subagentsMode`: `"Auto"`
  - `acpLastSelectedModel`: `"v1:6:custom:custom:gemini-ladder"`
  - `effortPerModel`, `ecoModePerModel`, `acpEcoModePerModel` set for built-in/BYOK models (custom `gemini-ladder` uses the proxy's tier routing instead).
- **`~/.junie/agents/*.md`**:
  - `task-dispatcher-planning.md`: pinned to `model: "custom:litellm-gemini-4-hydrogen-medium"`, `reasoningLevel: "high"` (note: the target deployment in `config.yaml` locks `reasoning_effort: medium`).
  - `task-dispatcher-implementation.md`: pinned to `model: "custom:litellm-gemini-4-hydrogen-low"`, `reasoningLevel: "low"`.
  - `task-dispatcher-verification.md`: pinned to `model: "custom:litellm-gemini-4-hydrogen-low"`, `reasoningLevel: "low"`.
- **`junie/rules/*.md` -> `~/.junie/AGENTS.md`**:
  - Compiled statically in sorted filename order into `~/.junie/AGENTS.md` (always added to Junie task context).
  - Skills (`docmancer`, etc.) use progressive disclosure (only name + description initially; full `SKILL.md` loaded on demand).

## Empirical Telemetry from Local Postgres (`LiteLLM_SpendLogs`)

### Cumulative Totals (All Logged Requests)

- `gemini/gemini-4-hydrogen` (`gemini-ladder`): 8,560 reqs, $89.02 spend, 219,672,066 prompt tokens, 188,405,699 cached tokens (**85.8% cache hit rate**), 3,749,777 completion tokens.
- `gemini/gemini-4-hydrogen` (`gemini-4-hydrogen-medium`, e.g., `task-dispatcher-planning`): 1,665 reqs, $15.66 spend, 45,020,700 prompt tokens, 39,932,042 cached tokens (**88.7% cache hit rate**), 670,306 completion tokens.
- `gemini/gemini-4-hydrogen` (`gemini-4-hydrogen-low`, e.g., `task-dispatcher-implementation` / `verification`): 1,169 reqs, $10.72 spend, 22,358,017 prompt tokens, 18,601,166 cached tokens (**83.2% cache hit rate**), 491,642 completion tokens.
- **Combined Hydrogen total:** **$115.40** across `11,394` logged requests (`$89.02 + $15.66 + $10.72`).
- `anthropic/claude-haiku-5-5` (`claude-haiku-5-5-low` via `fasterModel` + side-request hook): 1,149 reqs, $0.70 spend, 6,396,147 prompt tokens, 0 cached tokens reported in `prompt_tokens_details.cached_tokens`, 118,380 completion tokens.
- `hosted_vllm/gemini-decision-1`: 2,690 reqs, $0.00 logged by LiteLLM (cost entry absent for `hosted_vllm/`, estimated **~$1.57** at `$0.10/1M`), 15,697,653 input tokens (~5,835 input tokens/call average). Note: `gemini-decision-adapter` logs confirm it is actively serving `200 OK` requests on 2026-11-26 even though `LiteLLM_SpendLogs` stopped writing rows for `gemini-decision-1` after 2026-11-25.

### Recent 7-Day Breakdown Highlights (through 2026-11-26)

- **Reasoning tokens dominate output volume on Hydrogen:**
  - 2026-11-26 (`gemini-ladder`): 1,295,657 completion tokens, of which **938,525 (72.4%)** are reasoning tokens.
  - 2026-11-25 (`gemini-ladder`): 1,490,805 completion tokens, of which **1,069,239 (71.7%)** are reasoning tokens.
  - 2026-11-25 (`gemini-4-hydrogen-medium`): 507,395 completion tokens, of which **434,818 (85.7%)** are reasoning tokens.
  - 2026-11-25 (`gemini-4-hydrogen-low`): 446,044 completion tokens, of which **327,691 (73.5%)** are reasoning tokens.
- **Haiku side-requests also emit reasoning tokens:**
  - 2026-11-26 (`claude-haiku-5-5-low`): 22,026 completion tokens, of which **13,622 (61.8%)** are reasoning tokens.
  - 2026-11-25 (`claude-haiku-5-5-low`): 58,251 completion tokens, of which **39,314 (67.5%)** are reasoning tokens.

## Technical Constraints Discovered in LiteLLM + Junie

1. **Google GenAI passthrough (`apiType: "Google"`) silently ignores `config.yaml` `reasoning_effort` and `service_tier`:**
   - `~/.junie/models/gemini-ladder.json` and `litellm-gemini-4-hydrogen-{low,medium,high}.json` all use `apiType: "Google"` (`:generateContent`).
   - Inside the running `ghcr.io/berriai/litellm:main-stable` container (`litellm` version **`1.111.0`**):
     - `litellm/llms/gemini/chat/transformation.py` (OpenAI chat surface) supports `"service_tier"` and `"reasoning_effort"`.
     - `litellm/google_genai/main.py` and `litellm/llms/gemini/google_genai/transformation.py` (`GoogleGenAIConfig`) do **not** read `litellm_params.reasoning_effort` or `service_tier`.
     - `GoogleGenAIConfig.map_generate_content_optional_params` only copies keys from the client's `config` (`generationConfig`, which accepts `thinking_config` / `thinkingConfig`), and `get_generate_content_request_top_level_fields()` only forwards `('safetySettings', 'toolConfig', 'cachedContent', 'labels', 'continuationToken')`.
   - **Practical impact:** `reasoning_effort: low/medium/high` in `litellm-proxy/config.yaml` is not mapped into `generationConfig.thinkingConfig` on `:generateContent` by LiteLLM's Google GenAI handler. That aligns with telemetry on 2026-11-25 showing `gemini-4-hydrogen-low` still emitted **73.5% reasoning tokens** (`327,691 / 446,044`), `gemini-4-hydrogen-medium` emitted **85.7%** (`434,818 / 507,395`), and `gemini-ladder` emitted **71.7%**.
2. **Global rules vs progressive-disclosure skills size:**
   - `junie/rules/*.md` total ~2.5 KB across 31 lines (`bash-command-intent.md` 593 B, `docmancer-first.md` 1,402 B, `no-emdashes.md` 518 B), compiled deterministically in sorted order into `~/.junie/AGENTS.md`.
   - `docmancer/skills/docmancer/SKILL.md` is 5,720 B (109 lines), loaded only on demand via progressive disclosure.
3. **Spend breakdown math on `gemini-4-hydrogen` (`LiteLLM_SpendLogs`):**
   - Cumulative `gemini-ladder`: `$89.02` (`~$14.13` cached input at `188.4M * $0.075/1M`, `~$46.90` uncached input at `31.3M * $1.50/1M`, `~$28.12` output/thinking at `3.75M * $7.50/1M`).
   - On 2026-11-26 (`gemini-ladder`, `$26.23`): **~47% (`$12.26`)** was uncached input (`8.17M` tokens), **~37% (`$9.72`)** was output/thinking (`1.30M` tokens, of which **72.4%** were reasoning tokens), and **~16% (`$4.20`)** was cached input (`55.95M` tokens).

## Evaluation of Recommendations from `gemini_chat_transcript.md`

All recommendations below were extracted from [`gemini_chat_transcript.md`](./gemini_chat_transcript.md) and checked against the repository configuration, running container source, and Postgres telemetry.

### 1. Already Solved or Misdiagnosed in Your Current Setup

- **Trimming Decisions API payload (`classifier_context_window_size`):**
  - *Original recommendation (`gemini_chat_transcript.md`):* Trim `/v1beta/decisions` input to the last 1 to 3 turns instead of sending full history.
  - *Status:* Already configured (`classifier_context_window_size: 3` in `litellm-proxy/config.yaml`, lines 123 and 142). Average `gemini-decision-1` input is ~5,835 tokens/call (`15.70M` tokens across `2,690` logged calls = **~$1.57 total** at `$0.10/1M`, ~1.3% of Hydrogen spend).
- **Caching is "broken" / driving 0 to 50% hit rates:**
  - *Original recommendation (`gemini_chat_transcript.md`):* Check `cached_tokens`, because prefix cache breaks might be forcing full `$1.50/1M` rebills on every turn.
  - *Status:* Your cache hit rate is already **85.8%** overall on `gemini-ladder` (`87.3%` on Nov 26, `88.7%` on `medium`, `83.2%` on `low`), and `junie/rules/*.md` compiles deterministically into `~/.junie/AGENTS.md`. However, on Nov 26 (`64.1M` prompt tokens), the remaining **12.7% (`8.17M`) uncached input tokens** still cost **~$12.26/day** (**~47% of daily Hydrogen spend**), so protecting the 5-minute implicit cache TTL across 4 to 5 concurrent sessions remains worthwhile.
- **Pinning lightweight Junie side-requests (titles, summaries, capability filters):**
  - *Original recommendation (`gemini_chat_transcript.md`):* Downgrade trivial turns / side-requests to a cheaper fast model.
  - *Status:* Already solved via `~/.junie/models/gemini-ladder.json` (`fasterModel: claude-haiku-5-5-low`) and `litellm-proxy/custom_callbacks.py` (`TitleRoutingHook` pinning title/summary requests to `claude-haiku-5-5-low` and cleaning capability-filter outputs). Total `claude-haiku-5-5` spend is only **$0.70** across 1,149 requests. (Minor side note: `claude-haiku-5-5-low` shows `0` cached tokens and ~62 to 68% reasoning tokens on those 1,149 requests, though total dollar impact is under $1.)
- **Thinking tokens "aren't driving the bill":**
  - *Original claim (`gemini_chat_transcript.md`):* Gemini walked back its thinking-token warning once you mentioned using Decisions API routing for `low`/`medium`/`high`.
  - *Status:* Telemetry contradicts that walk-back. Output/thinking tokens are **32 to 37% of your Hydrogen spend** (`$28.12 / $89.02` cumulative on `gemini-ladder`; `$9.72 / $26.23` on Nov 26), and **72 to 86% of output tokens are reasoning tokens** even on `gemini-4-hydrogen-low`.
- **Separating API keys from sandboxed agents:**
  - *Original context (`gemini_chat_transcript.md`):* Keep `GEMINI_API_KEY` on the proxy.
  - *Status:* Already enforced by `litellm-proxy` (`~/litellm-proxy/.env`) and `safehouse/junie-safehouse` (`--env-pass` forwards only `LITELLM_MASTER_KEY`).

### 2. Relevant & High-Leverage for Your Current Config

- **Fix `reasoning_effort` propagation on `:generateContent` (`litellm-proxy`):**
  - **Highest-leverage config fix.** Because Junie uses `apiType: "Google"`, `reasoning_effort: low/medium/high` in `litellm-proxy/config.yaml` is not translated into `generationConfig.thinkingConfig` by LiteLLM `v1.111.0`'s `GoogleGenAIConfig` handler.
  - Either switching Junie's `gemini-ladder` profile to `apiType: "OpenAICompletion"` (where LiteLLM's `gemini/chat/transformation.py` natively supports `reasoning_effort` and `service_tier`) or injecting `generationConfig.thinkingConfig` per tier in `litellm-proxy/custom_callbacks.py` (or separate `thinkingConfig` overrides) would make `low` and `medium` tiers actually enforce lower thinking budgets. (Also check `task-dispatcher-planning.md`, which sets `reasoningLevel: "high"` while targeting `litellm-gemini-4-hydrogen-medium`, and keep `xhigh` disabled for routine coding as advised in `gemini_chat_transcript.md`.)
- **Managing the 5-minute implicit cache TTL across 4 to 5 concurrent sessions + batching/subagents (`junie/rules/` & `~/.junie/agents/`):**
  - Uncached input (`~13%` of prompt tokens) is **~47% of spend** (`$12.26` on Nov 26). Working in focused bursts on 1 to 2 active repos instead of rotating across 4 to 5 repos with >5-minute gaps avoids expiring the ~5-minute implicit cache prefix.
  - Adding concise guidance in `junie/rules/*.md` (compiled to `~/.junie/AGENTS.md`, not `.junie/guidelines.md` as `gemini_chat_transcript.md` suggested) to batch parallel file reads/searches and keep main-session exploration inside subagents returning lean summaries complements your existing `task-dispatcher-*` subagents (`~/.junie/agents/*.md`).
  - Note on `subagentsMode: "Auto"` in `~/.junie/settings.json`: Junie docs note that custom subagents ignore automatic tier selection and use their frontmatter `model` (or fall back to the main agent's model), so pinning `task-dispatcher-implementation` and `task-dispatcher-verification` explicitly in `~/.junie/agents/*.md` is already the right mechanism.

### 3. Partially Relevant (Needs Config Changes / Trade-offs First)

- **Flex inference (`service_tier: "flex"`, 50% discount) for background work:**
  - *Original recommendation (`gemini_chat_transcript.md`):* Route `low`/`medium` or non-blocking subagents to Flex (`$0.75/1M` input, `$3.75/1M` output, `$0.0375/1M` cached) with Standard fallbacks for `503`/`429` shedding and 600+ second client timeouts.
  - Not usable for interactive `gemini-ladder` coding due to 1 to 15 minute target latency and capacity shedding. Only fits fire-and-forget background runs or async verification (`task-dispatcher-verification.md` or a separate Junie custom model profile).
  - **Config blocker:** Your container runs LiteLLM `v1.111.0` (`gemini_chat_transcript.md` cited `v1.112.0+` for native `service_tier` -> `serviceTier` mapping), and `google_genai` (`apiType: "Google"`) does not support `service_tier` in `v1.111.0` (`gemini/chat` / `OpenAICompletion` does). The snippet in `gemini_chat_transcript.md` would silently drop `service_tier` on `apiType: "Google"`; using Flex requires either switching that profile to `apiType: "OpenAICompletion"` (with LiteLLM `1.112.0+` or verified `service_tier` passthrough) or injecting `serviceTier` on `:generateContent` via `custom_callbacks.py`.
- **Optional `gemini-4-neon` for `task-dispatcher-planning.md`:**
  - *Original recommendation (`gemini_chat_transcript.md`):* Wire `gemini/gemini-4-neon` (`$3.00` / `$15.00` per 1M, 2x Hydrogen) into the planner/architect tier only.
  - Easy to wire because `task-dispatcher-planning.md` already targets a dedicated deployment (`custom:litellm-gemini-4-hydrogen-medium`), which only accounted for **$15.66** (~13.6%) of Hydrogen spend. Only saves money net if better plans reduce downstream retry loops in `gemini-ladder` (`$89.02`) and `low` (`$10.72`).
- **Decisions API `session_affinity` / prompt-level pinning:**
  - `session_affinity: false` re-runs `gemini-decision-1` on every tool-call turn. At `~$1.57` total across 2,690 calls, token cost is tiny, though each call adds ~0.4 to 1.0s of sidecar/upstream latency before the main model call.

### 4. Not Relevant / Ruled Out

- **Downgrading low-complexity routes to `gemini-3.8-flash`:** Explicitly rejected by you in `gemini_chat_transcript.md` ("Gemini 4 only"), and trivial side-requests are already routed to `claude-haiku-5-5-low` (`$0.70` total).
- **Google AI Plus -> Pro/Ultra or Antigravity OAuth bridging / AI Studio free tier:** Consumer plans do not cover API traffic (`GEMINI_API_KEY` in `~/litellm-proxy/.env`), OAuth token extraction (`tokengateway` / `daily-cloudcode-pa.googleapis.com`) triggers `403 PERMISSION_DENIED` bans and lacks `/v1beta/decisions`, and AI Studio's free tier has far too low RPM/RPD caps (~5 to 10 RPM, ~20 to 250 RPD on Hydrogen, plus training-data privacy caveats) for 4 to 5 concurrent Junie sessions.
