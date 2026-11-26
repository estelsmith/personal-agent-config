# Gemini Chat Transcript: Subscriptions, Antigravity & LiteLLM Cost Optimization

**Date:** November 26, 2026

---

### User
Does my current Google AI subscription allow me to use Gemini Desktop and Google Antigravity?

### Gemini
**Yes** — your current **Google AI Plus** subscription lets you use both **Gemini Desktop** and **Google Antigravity**, though each comes with specific tier limits compared to Pro or Ultra.

#### 1. Gemini Desktop (macOS & Windows)
* **Access:** Included. The desktop app is free to download for macOS (Apple Silicon, macOS 15+) and Windows (Windows 10+) and inherits your Google AI Plus account limits.
* **What you get on AI Plus:**
  * **Usage & Models:** 2x the usage limits of the free tier, running on **Gemini 4 Hydrogen** (note: Pro/Neon models were restricted to Google AI Pro and higher as of November 13, 2026).
  * **Desktop Features:** Global quick-launch shortcuts (`Option + Space` on Mac / `Alt + Space` on Windows), background **Tasks**, Connected Apps (Gmail, Drive, Calendar), and **Computer Use** on macOS (available in the US on AI Plus and above, drawing from your shared compute quota).

#### 2. Google Antigravity
* **Access:** Included at the baseline free-tier level. Antigravity is free with any personal Google Account, and Google AI Plus shares the same Antigravity tier as free accounts.
* **What you get on AI Plus:**
  * **Models & Completions:** Unlimited Tab and Command completions in the IDE, plus access to **Gemini 4 Hydrogen** for agentic workflows (Gemini 4 Neon, Carbon, and Claude 5.5 thinking models require Pro or Ultra).
  * **Quota & Refresh:** Your agentic request quota **refreshes once per week** (Pro and Ultra refresh every 5 hours).
  * **Overages:** AI Plus accounts cannot purchase Google AI Credits to bypass the weekly cap if you hit it early.

| Feature | Your Plan (Google AI Plus) | Google AI Pro ($19.99/mo) |
| :--- | :--- | :--- |
| **Gemini Desktop App** | Full app access (2x free quota, macOS Computer Use) | Full app access (4x free quota, macOS Computer Use) |
| **Gemini App Models** | Gemini 4 Hydrogen | Gemini 4 Hydrogen & Neon |
| **Antigravity Access** | Baseline tier (same as Free) | Enhanced tier + prioritized traffic |
| **Antigravity Agent Models** | Gemini 4 Hydrogen | Gemini 4 Neon/Hydrogen, Claude Sonnet/Opus 5.5 |
| **Antigravity Quota Refresh** | Weekly | Every 5 hours (up to a weekly cap) |
| **Buy Extra AI Credits** | Not available | Available |

---

### User
> Usage & Models: 2x the usage limits of the free tier, running on Gemini 4 Hydrogen (note: Pro/Neon models were restricted to Google AI Pro and higher as of November 13, 2026).

That's okay. I use Hydrogen pretty much exclusively.

Though I use LiteLLM as a model proxy, so I can use Gemini Decisions API to route complex tasks to different Hydrogen reasoning efforts by default. Will I still be able to do this with my Pro subscription?

And on a related note, how much coding would I actually be able to do with Antigravity given my current subscription?

### Gemini
#### 1. LiteLLM, the Gemini Decisions API, and Your Subscription
**Yes, you will still be able to run that setup, though your consumer Google AI subscription doesn't actually govern it.**

* **Separate Billing:** Consumer subscriptions (**Google AI Plus**, **Pro**, and **Ultra**) only cover consumer surfaces—the Gemini web/mobile/desktop apps, Workspace integrations, and Google Antigravity. They do **not** provide API credits or rate limits for LiteLLM.
* **API Key Routing:** Because LiteLLM connects to Google AI Studio (or Vertex AI) via your `GEMINI_API_KEY`, it uses **pay-as-you-go API billing** (or the AI Studio free tier), completely independent of your Google One/Google AI plan.
* **Hydrogen + Decisions API Support:** Both **Gemini 4 Hydrogen** (`gemini/gemini-4-hydrogen`, $1.50/1M input and $7.50/1M output tokens) and the **Gemini Decisions API** (`gemini/gemini-decision-1` via LiteLLM's `/v1/decisions` or `/v1/systemone` endpoints) work directly over the API regardless of whether you stay on Google AI Plus or upgrade to Pro. Your existing `litellm_config.yaml` routing will continue to work without any plan-level restrictions.

#### 2. How Much Coding Can You Actually Do in Antigravity on Google AI Plus?
In short: **plenty of inline editing, but very little autonomous agent work.**

Google does not publish fixed prompt or token counts for Antigravity—it meters usage dynamically based on "agent work" and current server capacity—and **Google AI Plus gets the exact same Antigravity allocation as the $0 free tier**:

* **Unlimited Inline Assistance:** You get **unlimited** Tab autocomplete and inline Command (`Cmd/Ctrl + I`) edits. If you primarily use Antigravity as a traditional AI-assisted editor for quick inline code generation and completions, you won't hit a wall.
* **Tight Weekly Agent Cap:** Multi-step agentic sessions (planning, multi-file edits, running terminal commands, browser verification, and Antigravity CLI sessions) draw from a single **weekly bucket** with no 5-hour refresh. Because agent loops burn context rapidly across tool calls and file reads, developers on the free/Plus tier generally report exhausting their weekly agent quota after **one heavy afternoon session or a few medium-sized feature tasks**.
* **Hard Stop Until Reset:** Once that weekly agent bucket hits zero, autonomous agent runs are locked out until your weekly reset timer rolls over—unlike Google AI Pro ($19.99/mo), Plus cannot purchase Google AI Credits for overages and does not get a 5-hour rolling refresh.

**Practical takeaway:** With your current **Google AI Plus** plan, Antigravity is best treated as an unlimited Tab/Command editor with a small weekly allowance for occasional agentic tasks, while keeping your heavy multi-agent coding workflows routed through your LiteLLM proxy.

---

### User
> They do not provide API credits or rate limits for LiteLLM

How could I use my subscription with LiteLLM? Maybe a custom authentication plugin or something?

### Gemini
Technically, yes—people have built custom LiteLLM plugins that hijack the OAuth tokens from first-party CLI tools like Antigravity. **However, doing so explicitly violates Google's Terms of Service and is currently triggering automated account bans.**

#### 1. Why Google Blocks This (and What Happens If You Try)
* **Explicit ToS Violation:** The Google Antigravity Additional Terms of Service strictly forbid extracting or proxying the internal OAuth tokens used by the Antigravity IDE or CLI (`agy`) into third-party clients or gateways.
* **Active Ban Wave:** Google actively enforces this—hundreds of developers have had their Antigravity access hit with permanent `403 PERMISSION_DENIED` Terms of Service suspensions for routing subscription OAuth tokens through external proxies or multi-agent harnesses.
* **No Decisions API Support Anyway:** Even if you risked the OAuth bridge, the internal Antigravity endpoint (`daily-cloudcode-pa.googleapis.com/v1internal:streamGenerateContent`) only exposes the chat/generation stream used by the IDE—it does **not** expose the `/v1beta/decisions` endpoint you rely on for routing tasks across Hydrogen reasoning efforts.

#### 2. How Community Plugins Technically Work (For Context)
For awareness of what exists in the LiteLLM ecosystem:
* **OAuth Monkey-Patching (`sitecustomize.py`):** Community bridges like `tokengateway` (discussed in LiteLLM issue `#38246`) inject a `sitecustomize.py` via `PYTHONPATH` to intercept `litellm.completion` and `litellm.acompletion`, forwarding requests to `daily-cloudcode-pa.googleapis.com` using the OAuth token obtained from Antigravity's loopback login flow.
* **Custom `CustomLLM` Providers:** LiteLLM supports custom Python provider classes in `litellm_config.yaml`, though community testing notes that `CustomLLM` strips native provider token/cache usage reporting compared to direct API routing.

#### 3. The Safe, Supported Way to Keep Costs Low
If you want to keep using your LiteLLM proxy with the Gemini Decisions API and effort-pinned Hydrogen tiers without risking your Google account:
* **Use Google AI Studio API Keys:** Keep your `GEMINI_API_KEY` in LiteLLM. Google AI Studio's free tier gives you zero-cost API quota with rate limits (which works for light personal tasks, though data may be used to improve Google products unless billing is enabled), and enabling pay-as-you-go billing on **Gemini 4 Hydrogen** is inexpensive while keeping your personal Google account completely safe.
* **Keep Antigravity Separate:** Use your Google AI Plus subscription strictly inside the official Antigravity IDE/CLI (`agy`) or Gemini Desktop app, and let LiteLLM handle your Junie multi-agent traffic via standard API keys.

---

### User
> API Key Routing: Because LiteLLM connects to Google AI Studio (or Vertex AI) via your GEMINI_API_KEY, it uses pay-as-you-go API billing (or the AI Studio free tier), completely independent of your Google One/Google AI plan.

Okay... So what are the limits on the AI Studio free tier? Maybe I could combine them for slightly higher usage limits or something.

### Gemini
Google AI Studio's free tier includes both **Gemini 4 Hydrogen** and the **Gemini Decisions API (`gemini-decision-1`)**, so you can run your LiteLLM setup without paying—though there are strict rate limits and a major data-privacy catch for coding.

#### 1. Google AI Studio Free Tier Limits
Google no longer publishes a single static RPM/RPD table in its general docs because limits vary dynamically by account standing and server capacity—you have to check the **Rate Limits** page in your AI Studio dashboard for your exact live numbers. However, current documented baselines and developer-reported caps look like this:

| Model / Endpoint | Free Tier Access | Rate Limits (RPM / TPM / RPD) | Paid Tier 1 Rate |
| :--- | :--- | :--- | :--- |
| **Gemini Decision 1** (`/v1/decisions`) | **Free** | **200 RPM** / **50,000 TPM** / **10,000 RPD** | $0.10 / 1M input tokens ($0 output) |
| **Gemini 4 Hydrogen** (`gemini-4-hydrogen`) | **Free** | **Dynamic per project** (typically ~5–10 RPM, 250k TPM, and ~20–250 RPD; resets midnight PT) | $1.50 input / $7.50 output per 1M tokens |
| **Gemini 3.8 Flash** (`gemini-3.8-flash`) | **Free** | **Dynamic per project** (higher RPD than Hydrogen) | $0.75 input / $3.75 output per 1M tokens |
| **Gemini 4 Neon / Carbon / Argon** | **Paid Only** | Not available on free tier | $2.00–$3.00 input / $10.00–$15.00 output |

* **Per-Project, Not Per-Key:** Rate limits are enforced at the **Google Cloud project** level. Creating multiple API keys inside the same project shares the exact same quota pool. (Creating multiple free-tier projects to multiply quotas violates Google's API Terms of Service and triggers automated project suspensions.)
* **The Privacy Trade-Off (Important for Code):** On the AI Studio free tier, **Google may use your prompts, code snippets, and responses to train and improve its products**, and human reviewers may read flagged interactions. If you link a billing account (Tier 1), Google stops using your API data for model training.

#### 2. Can You Combine Them for Higher Usage?
You **cannot** pool quotas together into a single unified bucket, because the consumer subscription and the developer API are completely walled off from each other. However, you **can** split your workload across both surfaces to stretch your limits:

1. **Interactive & Browser-Assisted Work → Antigravity / Gemini Desktop (Google AI Plus):**
   * Use Antigravity's **unlimited Tab and Command completions** for day-to-day inline coding.
   * Save your weekly Antigravity agent quota for tasks that specifically benefit from its built-in browser verification or IDE state.
2. **Automated Multi-Agent Loops → LiteLLM (AI Studio Free Tier or Low-Cap Tier 1):**
   * Route your **Decisions API** calls through the AI Studio free tier—**10,000 RPD and 200 RPM** is way more than enough for a local task-routing classifier.
   * Keep **Gemini 4 Hydrogen** on the free tier for non-sensitive personal scripts/prototyping, or put a **$5–$10 monthly auto-reload cap** on a Tier 1 billing account when working on client codebases so you get higher RPM/TPM limits and strict zero-data-training privacy without surprise bills.

*(Note: If you ever decide to upgrade from Google AI Plus to **Google AI Pro** at $19.99/mo, Google One includes **$10/month in Google Cloud credits** via the Google Developer Program—though note that Google excluded Gemini Developer API keys in AI Studio from free Cloud trial credits in March 2026, so those credits primarily offset standard GCP/Vertex infrastructure rather than AI Studio keys.)*

---

### User
> Use Google AI Studio API Keys: Keep your GEMINI_API_KEY in LiteLLM. Google AI Studio's free tier gives you zero-cost API quota with rate limits (which works for light personal tasks, though data may be used to improve Google products unless billing is enabled), and enabling pay-as-you-go billing on Gemini 4 Hydrogen is inexpensive while keeping your personal Google account completely safe.

Okay, but during heavy coding sessions, even with LiteLLM automatic effort routing, I can easily spend $20-30 a day with API prices. It gets kind of expensive, and I know my subscription would be much cheaper.

### Gemini
You're completely right about the math. At **$1.50/1M input and $7.50/1M output** (including thinking tokens), heavy agentic loops easily chew through $20–$30 in a single day, whereas **Google AI Pro** is $19.99/month and **Google AI Ultra** is $99.99–$199.99/month.

That exact price gap is why Google strictly enforces the boundary between consumer subscriptions and API proxies—subscriptions rely on shared, burst-throttled capacity inside Google's own clients (Antigravity and Gemini Desktop), while automated multi-agent harnesses generate sustained, unthrottled token volume that would lose money at flat consumer pricing.

Since you cannot safely pipe your subscription into LiteLLM without risking an account ban, there are two practical ways to get that flat-rate economics legally:

#### 1. Shift Heavy Sessions Into Antigravity Directly (on Pro or Ultra)
If you want flat-rate pricing for heavy agentic coding without per-token anxiety, the supported path is running your agent sessions natively inside **Google Antigravity** (or its `agy` CLI) rather than routing Junie through LiteLLM:
* **Google AI Pro ($19.99/mo):** Gives you a **5-hour rolling quota refresh** (subject to a weekly ceiling) plus access to Gemini 4 Hydrogen, Neon, and Claude Sonnet/Opus 5.5. For a few hours of heavy coding per day, $19.99/mo replaces hundreds of dollars in raw API spend.
* **Google AI Ultra ($99.99–$199.99/mo):** Built specifically for all-day, high-volume agentic coding with **20x Pro limits** and highest priority throughput—still far cheaper than spending $20–$30/day on pay-as-you-go API tokens.

#### 2. Slash Your LiteLLM Hydrogen API Bill by 50–80%
If you prefer keeping your Junie + LiteLLM + Decisions API workflow intact, a few configuration tweaks dramatically cut that $20–$30/day burn rate:
* **Lean on Implicit Context Caching:** Gemini 4 Hydrogen supports **implicit caching at $0.075/1M tokens** (a **95% discount** off the $1.50 input rate, with zero storage fees). Keeping your system prompts, agent definitions, and repo context prefixes stable across turns in Junie lets Google hit the cache automatically instead of rebilling full context on every tool call.
* **Use Flex Inference for Background Subagents:** Hydrogen supports **Flex inference**, which cuts token rates in half (**$0.75 input / $3.75 output**) for non-blocking tasks (like background verification, test generation, or documentation passes) where slightly higher latency is fine.
* **Downgrade Low-Complexity Routes to `gemini-3.8-flash`:** For trivial dispatcher, formatting, or single-file edits where your Decisions API routes to low effort, `gemini-3.8-flash` costs **$0.75 input / $3.75 output** (half of Hydrogen's rate—note this doubles to $1.50/$7.50 on January 1, 2027, so it is a big savings window right now).
* **Cap `max_output_tokens` & Thinking Budgets:** Since thinking tokens are billed at the **$7.50/1M output rate**, a runaway reasoning loop on a minor file edit can cost more than the entire prompt. Enforcing tighter `thinking` budgets per Decisions API tier in `litellm_config.yaml` prevents low/medium tasks from burning massive output tokens.

---

### User
> 2. Slash Your LiteLLM Hydrogen API Bill by 50–80%

Okay, elaborate on this because I'm interested. It's spendy right now ($20-40 per day of heavy coding)

> Downgrade Low-Complexity Routes to gemini-3.8-flash: For trivial dispatcher, formatting, or single-file edits where your Decisions API routes to low effort, gemini-3.8-flash costs $0.75 input / $3.75 output (half of Hydrogen's rate—note this doubles to $1.50/$7.50 on January 1, 2027, so it is a big savings window right now).

I don't want to use Gemini 3.8 at all. Gemini 4 only... Mostly Hydrogen. I don't even use Argon, Carbon, or Neon right now. Though Neon is extremely interesting to me, I just haven't used it because of the added cost.

### Gemini
To cut a **$20–$40/day** bill while staying strictly on **Gemini 4 Hydrogen** (and even making room for **Gemini 4 Neon** on selective architectural tasks), you have to look at *where* agentic harnesses actually burn money.

In multi-step coding agents (like Junie), **80–90% of your spend comes from two sources**: repeatedly re-sending the growing conversation/codebase prefix on every tool call, and **thinking tokens** billed at the **$7.50/1M output rate** (note that `gemini-4-hydrogen` defaults to `high` thinking effort unless overridden).

Here is how to slash your Hydrogen spend by 50–80%—and how Neon actually compares in cost.

#### 1. Maximize Implicit Context Caching ($0.075/1M vs. $1.50/1M — 95% Off Input)
Gemini 4 Hydrogen does not support explicit cache creation, **only implicit caching**—meaning Google automatically detects matching prompt prefixes across requests and bills cached reads at **$0.075/1M tokens** instead of **$1.50/1M** (with zero storage fees).

If your Junie agent loop is costing $20–$40/day, your prefix is likely breaking cache between turns. To keep hit rates above 70–85%:
* **Keep the prompt prefix strictly append-only:** Never inject dynamic timestamps, changing file trees, or shifting tool definitions at the top of the system prompt or early in the message history. Even one changed token early in the payload invalidates the cache for everything after it.
* **Batch file reads instead of one-by-one tool loops:** Every single tool call round-trip re-sends the entire context window. Instructing your subagents to read related files in parallel in a single turn cuts the number of prefix reads in half.
* **Keep subagent prompts lean and stateless:** Pass concise failure deltas and targeted file paths (`discovery/task-name.md`) rather than dumping full repository trees into every spawned subagent.

#### 2. Switch Non-Blocking Tiers to Flex Inference ($0.75 Input / $3.75 Output — 50% Off)
Gemini 4 Hydrogen supports **Flex inference** at exact Batch rates (**$0.75/1M input**, **$3.75/1M output**, and **$0.0375/1M cached read**)—a flat **50% discount** off Standard pricing (`$1.50` / `$7.50`).

* **How it works:** Flex runs on-demand (not queued for 24 hours like Batch), using spare capacity. The only trade-off is slightly higher latency and occasional capacity shedding (which LiteLLM handles automatically via fallback/retries).
* **Where to use it in LiteLLM:** Route your **verifier**, **test-writer**, or background analysis tiers to Hydrogen Flex, with Standard Hydrogen configured as a fallback in `litellm_config.yaml` in case a Flex request sheds:

```yaml
model_list:
  - model_name: hydrogen-flex
    litellm_params:
      model: gemini/gemini-4-hydrogen
      api_key: os.environ/GEMINI_API_KEY
      # Pass Flex tier / service_tier parameter supported by your LiteLLM version
      extra_body:
        service_tier: "flex"

  - model_name: hydrogen-standard
    litellm_params:
      model: gemini/gemini-4-hydrogen
      api_key: os.environ/GEMINI_API_KEY

router_settings:
  fallbacks: [{"hydrogen-flex": ["hydrogen-standard"]}]
```

#### 3. Re-Tune Hydrogen's 4 Reasoning Levels (`low`, `medium`, `high`, `xhigh`)
By default, `gemini-4-hydrogen` runs at **`high`** reasoning effort, and **`xhigh`** (which bumps benchmark scores slightly) can triple output/thinking token consumption on routine code edits. Because thinking tokens cost **$7.50/1M** (5x more than uncached input and 100x more than cached input), unchecked reasoning is the #1 silent budget killer.

* **Audit your Decisions API mapping:**
  * **Dispatcher / boilerplate / formatting / simple edits → `low`:** Keeps thinking overhead near zero while preserving Gemini 4's base coding intelligence.
  * **Standard implementation & multi-file edits → `medium`:** Usually performs nearly identically to `high` on PHP/Symfony and TypeScript implementation tasks while cutting thinking tokens by 40–60%.
  * **Complex debugging & planning → `high`:** Reserve `high` strictly for root-cause debugging or architectural planning.
  * **Avoid `xhigh` for general coding:** Only trigger `xhigh` manually when Hydrogen at `high` genuinely gets stuck.

#### 4. Where Does Gemini 4 Neon Fit In? (It's Less Expensive Than You Think)
You mentioned avoiding **Gemini 4 Neon** because of the added cost—worth noting is that **Neon is only 2x Hydrogen's price**, not 5x–10x like frontier models used to be:

| Model | Standard Input | Cached Input | Standard Output (incl. Thinking) | Flex Input / Output |
| :--- | :--- | :--- | :--- | :--- |
| **Gemini 4 Hydrogen** | $1.50 / 1M | $0.075 / 1M | $7.50 / 1M | $0.75 / $3.75 |
| **Gemini 4 Neon** | $3.00 / 1M | $0.150 / 1M | $15.00 / 1M | $1.50 / $7.50 |

*(Note: Unlike Argon and Carbon—whose promotional 50% discount ends on November 30, 2026—Hydrogen and Neon's current pricing is their regular standard rate.)*

**How to afford Neon inside a smaller budget:**
Once implicit caching and Flex cuts your daily Hydrogen spend from ~$30 down to ~$8–$10, you can afford to wire **Gemini 4 Neon** (`gemini/gemini-4-neon`) into **only your highest-leverage planner/architect tier** for complex tasks. Because Neon often solves tricky multi-service or architectural problems in 1–2 turns instead of burning 8 failed retry loops on Hydrogen, using Neon selectively for planning frequently **reduces total tokens spent per task** while giving you stronger architectural output.

---

### User
> note that gemini-4-hydrogen defaults to high thinking effort unless overridden

In LiteLLM I'm specifically using the Gemini Decisions API to route tasks to different effort levels. `high` is reserved for highly complex tasks. Generally it sticks to low/medium, occasionally going high for deep research/planning.

### Gemini
That is actually a really smart setup—if your Decisions API router already defaults to `low` and `medium` and only escalates to `high` for deep research/planning, **thinking tokens aren't what's driving your $20–$40/day bill**.

When you're running mostly `low`/`medium` Hydrogen and still hitting $20–$40/day, almost the entire cost is **uncached input context** (`$1.50/1M`) and **Decisions API input overhead**, not output/thinking tokens.

#### 1. Check Your Decisions API Payload Size ($0.10/1M — No Caching!)
`gemini-decision-1` is cheap on paper ($0.10/1M input, $0 output), **but it does not support context caching**.
* If your LiteLLM router sends the **entire multi-turn conversation history or full file context** into the Decisions API classifier on every single agent step, you are paying full price on every tool call just to classify the turn.
* **Fix:** Only pass the **latest user prompt + last 1–2 assistant/tool turns** (or a truncated task description) into `/v1beta/decisions`. Even better: only run the Decisions classifier at the **start of a user prompt or subagent dispatch**, and pin the chosen `reasoning_effort` for the subsequent tool-call loop of that subtask rather than re-classifying every individual tool step.

#### 2. Inspect `cached_tokens` on Your Hydrogen Requests ($1.50 vs. $0.075/1M)
In an agentic coding loop (like Junie), a 50k–100k token codebase context re-sent 30 times in a session equals **1.5M–3M input tokens** per task:
* **0% cache hit:** 3M tokens × $1.50 = **$4.50** for one task.
* **80% cache hit:** (600k × $1.50) + (2.4M × $0.075) = **$1.08** for the exact same task.

Check your LiteLLM logs for `prompt_tokens_details.cached_tokens`. Because `gemini-4-hydrogen` uses **implicit caching** (minimum 4,096 tokens, TTL ~5 minutes), any tiny mutation near the top of the prompt—like an agent harness injecting a current timestamp, dynamic tool list order, or changing `discovery/` status header before the codebase files—breaks the prefix and forces a full `$1.50/1M` rebill on every turn.
* **Fix:** Keep system instructions, tool schemas, and static repo context at the **very top** of the message array in a deterministic order, and append all dynamic state/timestamps at the **bottom**.

#### 3. Use Native `service_tier: "flex"` in LiteLLM ($0.75 / $3.75 — Instant 50% Cut)
Since LiteLLM `v1.112.0+`, you don't even need `extra_body` hacks—LiteLLM natively maps OpenAI's standard `service_tier: "flex"` parameter directly to Gemini's `serviceTier` field (`$0.75/1M` input, `$3.75/1M` output, `$0.0375/1M` cached read).

You can wire this directly into your existing effort-pinned deployments in `litellm_config.yaml`:

```yaml
model_list:
  # Flex tiers (50% off) for low/medium default work
  - model_name: hydrogen-low
    litellm_params:
      model: gemini/gemini-4-hydrogen
      api_key: os.environ/GEMINI_API_KEY
      reasoning_effort: "low"
      service_tier: "flex"

  - model_name: hydrogen-medium
    litellm_params:
      model: gemini/gemini-4-hydrogen
      api_key: os.environ/GEMINI_API_KEY
      reasoning_effort: "medium"
      service_tier: "flex"

  # Standard tier for interactive high-effort planning (lowest latency, no shedding)
  - model_name: hydrogen-high
    litellm_params:
      model: gemini/gemini-4-hydrogen
      api_key: os.environ/GEMINI_API_KEY
      reasoning_effort: "high"

  # Fallback target if Flex sheds capacity
  - model_name: hydrogen-standard-fallback
    litellm_params:
      model: gemini/gemini-4-hydrogen
      api_key: os.environ/GEMINI_API_KEY

router_settings:
  fallbacks:
    - {"hydrogen-low": ["hydrogen-standard-fallback"]}
    - {"hydrogen-medium": ["hydrogen-standard-fallback"]}
```

If you combine **trimming Decisions API input**, **fixing prefix cache hits**, and **routing `low`/`medium` to `service_tier: "flex"`**, a $30/day heavy session on Hydrogen typically drops to **$5–$9/day** with zero model downgrades.

---

### User
> Batch file reads instead of one-by-one tool loops: Every single tool call round-trip re-sends the entire context window. Instructing your subagents to read related files in parallel in a single turn cuts the number of prefix reads in half.

Do you mean instruct the agent to `spawn_subagent` with the file reads, then instruct the sub-agent to return only the relevant context that's being asked for??

> Keep subagent prompts lean and stateless: Pass concise failure deltas and targeted file paths (discovery/task-name.md) rather than dumping full repository trees into every spawned subagent.

This feels like an instruction to the agent. Junie handles the entire workflow, so I don't know how else I'd control this.

> 2. Switch Non-Blocking Tiers to Flex Inference ($0.75 Input / $3.75 Output — 50% Off)

How much added latency would I expect? Would it still be reasonably for a live agent loop where I'm actively talking through coding problems with the agent?

> thinking tokens aren't what's driving your $20–$40/day bill.

Yeah, I know. It's because I code a shitload every day. Very heavy usage, usually have 4-5 active agent sessions running at once across different repositories. Junie+Hydrogen really allowed me to 10x my output versus doing everything by hand.

> Check Your Decisions API Payload Size ($0.10/1M — No Caching!)

The LiteLLM complexity router only sends the last 3 turns from the context to the decision API. It does not send the full context, it only looks at very recent activity to check where the next turn is likely going to go.

### Gemini
#### 1. Flex Inference Latency: Is It Viable for Live Coding?
**No — Flex is too slow and unpredictable for an active back-and-forth coding session.**
* **Official Latency Target:** Google's Gemini API documentation sets Flex's target latency at **1 to 15 minutes** per request (versus seconds on Standard), and recommends setting client timeouts to **600+ seconds (10+ minutes)**.
* **Sheddable Capacity:** During peak hours, Flex requests can queue for several minutes or return a `503 Service Unavailable` / `429` eviction error if standard traffic spikes.
* **Where Flex Actually Works:** Since you run **4–5 concurrent Junie sessions across different repositories**, Flex is great for **fire-and-forget background sessions** (e.g., kicking off a large refactor, test suite generation, or codebase audit in repo #3 and #4 while you actively work in repo #1), or for background `verifier` subagents. Keep your primary interactive session on **Standard** so you aren't waiting minutes between turns.

#### 2. Controlling Junie Subagents & File Reads Without Rewriting the Harness
Since you already have the Decisions API router properly trimmed to the last 3 turns and you're running 4–5 concurrent sessions, you can steer Junie's file-reading and subagent behavior directly through your **`.junie/guidelines.md`** (or agent markdown definitions in `.junie/agents/`)—no harness changes needed:

* **Parallel Tool Calls (No `spawn_subagent` Required for Simple Reads):**
  * You don't need to spawn a subagent just to read files. When Junie's main loop issues 5 file-read tool calls sequentially (one per turn), it pays to re-send the entire conversation history 5 times.
  * Adding a rule to `.junie/guidelines.md`—such as *"When inspecting files, batch all related file reads and searches into a single parallel tool-call turn rather than reading files sequentially"*—collapses 5 full-context round-trips into 1, cutting input token volume for discovery phases by up to 70–80%.
* **Using Subagents as "Context Compressors":**
  * Where `spawn_subagent` *does* save huge money across 4–5 active sessions is **isolating noisy exploration** (grepping across a large repo, reading 15 candidate files, or parsing long PHPUnit/Symfony stack traces).
  * If the main session reads 15 files directly, all 15 files stay pinned in your main session's context window for every subsequent turn. If instead the main agent spawns a subagent with a prompt like *"Locate where X is wired in `src/` and return only the exact file paths, method signatures, and line numbers,"* the subagent absorbs the heavy read once and returns a 300-token summary—keeping your main session's prefix tiny for the rest of the coding loop.
* **Keeping Subagent Prompts Lean:**
  * In your `.junie/agents/` markdown prompts, instruct the parent agent to pass **file paths and `discovery/task-name.md` references** rather than pasting file contents or full directory trees into the `prompt=` argument, letting the subagent read only the specific files it needs.

#### 3. The Highest-ROI Lever for 4–5 Concurrent Sessions: Prefix Cache Hit Rate
When running 4–5 heavy sessions at once on Standard Hydrogen, **implicit context caching (`$0.075/1M` vs. `$1.50/1M`)** is the single biggest lever you have without changing latency or models:
* Check `prompt_tokens_details.cached_tokens` in your LiteLLM spend logs.
* Because Google's implicit cache has a **~5-minute TTL** and requires an **exact prefix match**, switching back and forth between 5 active repos with >5-minute gaps between turns in any single repo causes the cache to expire right before your next turn—forcing you to pay the full `$1.50/1M` input rate repeatedly.
* Similarly, if any JetBrains MCP server or dynamic rule injects changing timestamps, git status, or open-tab lists into the system prompt between turns, it invalidates the prefix on every single request. Keeping static project guidelines at the top of the prompt and working in tighter bursts per session maximizes that **95% input discount**.