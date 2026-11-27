# Personal Voice & Writing Style Research

Analysis of your speaking and writing style across recent Junie sessions, LiteLLM request logs, Gemini Desktop chat transcripts, Google Takeout Gemini Apps history, and repository documentation, paired with the compiled global rule in [`junie/rules/personal-voice.md`](../../junie/rules/personal-voice.md) and local sample tracking in [`samples/README.md`](./samples/README.md).

> **Note on sample archives:** The exported prompt files (`junie-and-litellm-prompts.md`, `gemini-chat-transcript-prompts.md`, `gemini-apps-takeout-prompts.md`, and `running-log.md`) are gitignored via [`samples/.gitignore`](./samples/.gitignore) so personal chat logs stay local on disk rather than in Git history. Sample citations below (e.g., `` `junie-and-litellm-prompts.md` #021 ``) refer to those local archives.

## 1. Corpus & Sources Analyzed

### Accessible & Included Sources

| Source | Time Window | Volume Analyzed | Notes |
| --- | --- | --- | --- |
| Junie session transcripts (`~/.junie/sessions/`) | `2026-11-18` to `2026-11-26` | **82 sessions**, **393** unique clean user turns | Spans 6 repositories: `engage` (`122`), `kalshibot-btc-15m` (`96`), `personal-agent-config` (`83` from sessions + `3` LiteLLM-unique), `microboat` (`53`), `task-dispatcher` (`36`), and `litellm-proxy` (`3`). |
| LiteLLM Postgres logs (`LiteLLM_SpendLogs`) | `2026-11-26` (`01:18` to `23:13 UTC`) | **3,000** logged calls (`3` additional live turns not yet in the Junie snapshot) | Mostly mirrors Junie traffic (`gemini-ladder`, `claude-haiku-5-5-low` capability-filter `<user_request>` blocks, and title hooks), while capturing active-session prompts in real time. |
| Exported Gemini Desktop transcript (`research/gemini-cost-reduction/gemini_chat_transcript.md`) | `2026-11-26` | **8** user turns | Captures longer conversational reasoning with Gemini Desktop (where phrases like `spendy`, `Though ...`, and `??` double question marks appeared). |
| Google Takeout Gemini Apps history (`/Users/esmith/Desktop/Takeout/My Activity/Gemini Apps/MyActivity.html`) | `2026-08-19` to `2026-11-26` | **395** unique clean user turns (`409` raw `Prompted` entries) | Expands the corpus across 4 months of Gemini Desktop and spoken/voice-dictated chats (after deduplicating the `8` overlapping turns from `gemini_chat_transcript.md`, `1` internal repeat, `2` pasted AI-formatted profile/log blocks, `2` raw IDE error dumps, and `1` code-only paste). |
| Repository prose & notes (`README.md`, `wishlist.md`, `junie/rules/*.md`, subsystem READMEs) | Current repo state | **11** files | Provides direct examples of your unassisted personal notes (`wishlist.md`) alongside README revisions you explicitly steered and approved. |

### Checked Local Stores Without Usable History

- **Gemini Desktop (`com.google.GeminiMacOS`):** Local storage in `~/Library/Caches/com.google.GeminiMacOS/Gemini/user1/ChatInfo2.store` (`ZCHATINFOSTOREDMODEL` and `ZCHATMESSAGESTOREDMODEL`) caches only 50 messages (25 user turns across 103 chat entries), and message payloads live in `ZENCRYPTEDPROTOBYTES` blobs (header `0xCAFEBA2E`) encrypted at rest with a Keychain-backed key. Exporting via Google Takeout resolved this gap and provided the full `2026-08-19` to `2026-11-26` Gemini Apps history.
- **Gemini Desktop diagnostic logs:** Files under `~/Library/Caches/com.google.GeminiMacOS/Logs/` redact user prompt bodies (`Starting new persistent chat [REDACTED]`).
- **Antigravity local DBs:** Checked `~/.gemini/antigravity/conversations/` and `~/.gemini/antigravity-acp/conversations/`. Only `18b6317e-02e4-4252-9b71-a0eb5b1298b1.db` held user turns, and it is a 3-turn sanity check (`"Helloooo, are you there?"`, `"What model are you running?"`, and `"Where can I see my current antigravity usage limits?"`).

## 2. Quantitative Linguistic Profile

Measured across all **799** clean, deduplicated user-voice samples in the local [`samples/`](./samples/README.md) archive (`396` Junie/LiteLLM samples + `8` Gemini Desktop transcript turns + `395` Google Takeout Gemini Apps turns):

- **Corpus size:** `22,512` words across `1,807` sentences (`13,572` words / `1,074` sentences in Junie/LiteLLM + Gemini transcript; `8,940` words / `733` sentences in Google Takeout).
- **Turn length:** Mean `28.2` words per turn (median `20`, max `251`). Gemini Apps queries are noticeably punchier (mean `22.6` words/turn, median `16`) than Junie coding prompts (mean `33.6` words/turn, median `24`), reinforcing that you steer in tight, focused bursts rather than walls of text.
- **Sentence length:** Mean `12.5` words per sentence (median `11`). Gemini Apps averages `12.2` words/sentence (median `10`), and Junie/LiteLLM + transcript averages `12.6` words/sentence (median `11`).
- **Contraction rate:** **88.9%** contracted across the full corpus (`507` contracted forms vs. `63` uncontracted equivalents across 26 tracked pairs, normalizing straight and curly apostrophes). Key ratios:
  - `I'm` (`91`) vs. `I am` (`1`)
  - `don't` (`70`) vs. `do not` (`1`)
  - `it's` (`66`) vs. `it is` (`2`)
  - `what's` (`36`) vs. `what is` (`4`)
  - `doesn't` (`27`) vs. `does not` (`3`)
  - `let's` (`23`) vs. `let us` (`0`)
  - `isn't` (`14`) vs. `is not` (`3`)
  - `can't` (`13`) vs. `cannot`/`can not` (`3`)
  - `shouldn't` (`12`) vs. `should not` (`1`)
  - `wouldn't` (`10`) vs. `would not` (`0`), `won't` (`8`) vs. `will not` (`0`), `didn't` (`6`) vs. `did not` (`0`)
- **Zero emdashes:** `0` occurrences of `U+2014` and `0` prose `--` stand-ins across all `22,512` words of your prompts and across all repo-authored docs (the only ` -- ` strings in Junie samples are CLI `mise exec -- ...` flags inside backticks, and the only emdashes in raw exports came from AI responses or pasted `>` blockquotes).
- **Near-zero exclamation marks:** Only `1` exclamation mark across `799` prompts (`"Great, this finally works. Thank you!"` in `gemini-apps-takeout-prompts.md` #098 after resolving a multi-turn Ollama/Junie setup issue).
- **High question density:** `567` question marks across `799` prompts (`303` in Junie/LiteLLM + `264` in Takeout), including `63` sentences starting with `Can you` or `Can we` and `18` negative questions (`Wouldn't ...`, `Won't ...`, `Can't ...`, `Shouldn't ...`, `Doesn't ...`, `Are you not ...`, `Can you not ...`).
- **Parentheticals over dashes:** `133` parenthetical `(...)` groups (`53` in Junie/LiteLLM + chat, `80` in Takeout) used to tuck in examples, file paths, `(think ...)` mental anchors, or side context without breaking sentence flow.
- **Spoken/voice-dictated turns:** `33` occurrences of `uh`/`um` across early Takeout chats (`2026-08`), confirming that even when speaking aloud to Gemini rather than typing, your phrasing habits (`Instead of X`, `that way`, `So ...`, `Okay, well, ...`) stay intact.

## 3. Core Personality & Register Calibration

Your voice is grounded, practical, and candid. You sound like a senior engineer thinking out loud or walking a teammate through a design at their desk, never like a presenter reading slides.

### Register Shifting Across Contexts

Your underlying directness stays constant, while word choice shifts cleanly across four registers:

| Context | Examples | Tone & Pronouns | What Changes |
| --- | --- | --- | --- |
| **Live chat & agent steering** | Junie prompts, Gemini Desktop | Direct, conversational, collaborative (`we`, `I`, `let's`, `Can we...`) | Frequent `Okay...`, `Alright`, ellipses, `??` for emphasis, comma splices, occasional dropped subjects (`"Very heavy usage, usually have..."`), and casual bluntness (`sucks`, `ugh`, `nah`). |
| **Personal notes & backlog** | `wishlist.md` | First-person, dryly self-deprecating, unfiltered (`I`, `my`) | Candidly calls out pain points and AI debt (`"The CLI tooling for doctor/install is pretty garbage"`, `"LLMs can reason about this shit but humans can't"`, `"Not very human-friendly"`). |
| **Personal repo READMEs** | `README.md`, `safehouse/README.md`, `junie/README.md` | First-person ownership (`"This is my personal..."`, `"I built it so I can..."`) | Plainspoken and approachable without slang or profanity. Explains *why* tools exist and *what* tradeoffs they carry, inviting readers to borrow ideas (`"feel free to take ideas from it"`). |
| **Work / teammate prose** | `engage` docblocks, Slack release summaries | Plainspoken `we` or neutral imperative | Short 1 to 2 sentence explanations focused on why a workaround exists, zero filler, and Slack-safe Markdown formatting. |

### Key Personality Traits

- **Strong personal ownership:** In `junie-and-litellm-prompts.md` #345, you pushed back directly on sterile phrasing: `"Also, this isn't just 'a' modular agent config repository. It's MY agent config repository. It's for me and me alone. Though I might open-source it so others can take ideas from it for their own agents."`
- **Allergy to hype, badges, and corporate filler:** You immediately stripped a `"DECLARATIVE AGENT CONFIG"` SVG badge because `"it's kind of cheesy"` (`junie-and-litellm-prompts.md` #351), and your published docs avoid buzzwords, exclamation points, and celebratory prose.
- **Dry, matter-of-fact candor:** When something is weak or broken, you say so plainly without theatrics:
  - `"Haiku is not a very strong model, and often gets things wrong. ... As a matter of fact, Haiku kind of sucks in general. It's fast, but deviates from instructions rather frequently."` (`junie-and-litellm-prompts.md` #274)
  - `"The code quality, for example, is pretty low."` (`junie-and-litellm-prompts.md` #052)
  - `"It's good to have it hardened against weird hard-to-reproduce errors."` (`junie-and-litellm-prompts.md` #197)
- **Anti-overengineering pragmatism:** You push back on unnecessary complexity, look for practical sufficiency, and set crisp non-goals (`"I don't need to get fancy, bash does most of what I'd need"` in `gemini-apps-takeout-prompts.md` #384, `"Maybe that's good enough?"` in #256, `"Would it materially make a difference?"` in #249 and #254, `"I don't want anything leaking into the system-level"` in #366, and `"Not very human-friendly"` in `wishlist.md`).

## 4. Speaking Rhythm & Verbal Mannerisms

Every pattern below appeared repeatedly across your prompts and notes:

| Pattern | Corpus Frequency | How You Use It | Verbatim Examples |
| --- | --- | --- | --- |
| **Sentence-initial `Though`** | `18` starters (`25` total `though`) | Signature pivot to introduce a caveat, refinement, or exception right after stating the main point. | `"In PostHogAdapter::capture(), let's go with the $set option. Though we don't need it as a separate variable, it can be inlined into properties."` (`junie-and-litellm-prompts.md` #021) / `"Though now that you mention it, I'm curious about these other tools."` (`gemini-apps-takeout-prompts.md` #366) / `"Though it sucks to split my workflow up like this."` (`gemini-apps-takeout-prompts.md` #389) |
| **`Instead of X`, `rather than Y`, and `Not X, Y` exclusions** | `29` `instead of`, `4` `rather than`, frequent `Not X` | Contrasts the chosen design directly against what you rejected or explicitly rules out non-goals. | `"Instead of chasing streaks, it should wait until the market opens..."` (`junie-and-litellm-prompts.md` #049) / `"Not n8n, but the same workflow as windmill that's much smaller/efficient."` (`gemini-apps-takeout-prompts.md` #301) / `"I'm only interested in running this through Mise. Don't show me anything about homebrew."` (`gemini-apps-takeout-prompts.md` #380) |
| **Terse `X vs Y` / `versus` comparisons** | `25` `vs`/`versus` (`20` in Takeout) | Opens evaluations with ultra-short `A vs B` prompts or weighs tradeoffs directly with `versus`. | `"fx vs pi agent harnesses"` (`gemini-apps-takeout-prompts.md` #279) / `"docmancer vs graphify"` (`gemini-apps-takeout-prompts.md` #341) / `"...pricing differences versus comparable capabilities."` (`gemini-apps-takeout-prompts.md` #258) |
| **Negative-question assumption checks** | `18` questions (`5` `??` markers) | Challenges an assumption or nudges toward a simpler design with `Wouldn't`, `Won't`, `Can't`, `Shouldn't`, or `Doesn't`. | `"Wouldn't it be better if it were markdown or something?"` (`gemini-apps-takeout-prompts.md` #120) / `"Won't memory grow endlessly by storing it as a single object like this?"` (`junie-and-litellm-prompts.md` #070) / `"Can't mise have a task that runs mise upgrade ollama followed by the launchctl command??"` (`gemini-apps-takeout-prompts.md` #381) |
| **Context-first framing (`Since`, `Given`, `With that said`, `Effectively`, `Specifically`)** | `31` `since`, `13` `given`, `6` `with this/that said`, `24` `specifically`, `1` `effectively` | Grounds a rule or request in practical cause before stating the action or conclusion. | `"Effectively, we're recording the number of records returned..."` (`junie-and-litellm-prompts.md` #008) / `"With this said, the default database path should look at the XDG application root..."` (`junie-and-litellm-prompts.md` #261) / `"Specifically, I’m using Gemini and Junie to extract my personal voice..."` (`gemini-apps-takeout-prompts.md` #395) |
| **Hypothetical & sequenced spec openers (`Basically`, `Say ...`, `Also / Finally / Lastly`, `Turns out`)** | `5` `basically`, `3` `Say ...`, `9` `that way`, `1` `turns out` | Sets up concrete scenarios quickly or lays out requirements in clean sequence. | `"Say I'm writing bash scripts that may not be created by my shell (think an AI agent)."` (`gemini-apps-takeout-prompts.md` #367) / `"Turns out I'm already getting [redacted-supplement] in my multivitamin."` (`gemini-apps-takeout-prompts.md` #173) / `"Basically I'm looking for these things:"` (`gemini-apps-takeout-prompts.md` #384) |
| **Concrete grounding (`like`, `for example`, `(think ...)`)** | `138` `like`, `11` `for example`, `2` `(think ...)` (`0` `such as`) | Follows an abstract statement right away with a tangible example (note that `such as` never appears in your 799-sample corpus). | `"It should randomly do things like make an attorney search (/v1/attorneys), do some optional filtering, maybe a couple of pagination requests..."` (`junie-and-litellm-prompts.md` #014) / `"...hardware-enforced VM boundaries (think firecracker)..."` (`gemini-apps-takeout-prompts.md` #293) |
| **Parenthetical asides `(...)`** | `133` groups | Drops paths, examples, and secondary caveats inline without interrupting sentence momentum or using emdashes. | `"...test this flow before and after changes in this branch (HEAD..develop)..."` (`junie-and-litellm-prompts.md` #037) / `"Read .task-dispatcher.json (no yaml)."` (`junie-and-litellm-prompts.md` #290) |
| **Measured hedging when uncertain** | `36` `maybe`, `33` `I think`, `15` `probably`, `12` `unsure`, `12` `seems/looks like` | Avoids false certainty when hypothesizing (`"I'm pretty sure"`, `"I'm unsure"`, `"probably"`, `"seems like"`). | `"Sessions get started on /login I'm pretty sure..."` (`junie-and-litellm-prompts.md` #033) / `"Though we probably want to note its behavior in README..."` (`junie-and-litellm-prompts.md` #064) / `"It gets kind of expensive..."` (`gemini-chat-transcript-prompts.md` Turn 05) |
| **Transition & course-correction openers** | `147` `so`, `22` `actually`, `23` `okay`, `6` `alright` | Starts new turns conversationally (`Okay, ...`, `Alright, ...`, `Actually, ...`, `So ...`). | `"Actually, instead of putting engage-report in the filename, we add it as a tag."` (`junie-and-litellm-prompts.md` #005) / `"Alright, let's remove the --db argument from all commands."` (`junie-and-litellm-prompts.md` #261) |
| **Short anchor takeaways & check-ins** | `9` `make/makes sense`, `12` `How/What about`, frequent short closers | Ends multi-sentence thoughts with a brief punchy summary or sanity check. | `"Does it make sense? Any suggestions?"` (`junie-and-litellm-prompts.md` #005) / `"Simple is better."` / `"They're also good escape-hatches for whenever I break gemini-ladder..."` (`junie-and-litellm-prompts.md` #221) |
| **Conversational pacing (chat only)** | Observed in Gemini & live Junie | Clipped subject-drops, comma splices, and raw casual reactions (`bro`, `tf`, `Ugh`, `Nah`, `Orrr..`) when thinking fast; keep these in casual chat and clean them up into crisp short sentences in docs. | `"The baby, bro... Now it's a dude, tf"` (`gemini-apps-takeout-prompts.md` #076) / `"Nah, I’m good. Thanks."` (`gemini-apps-takeout-prompts.md` #389) / `"Orrr.. I could buy a 30lb kettlebell."` (`gemini-apps-takeout-prompts.md` #337) |

### Vocabulary & Tactile Engineering Idioms

You prefer everyday, mechanical words over abstract terminology:

- **Cost & resource behavior:** `spendy` (`"It's spendy right now ($20-40 per day of heavy coding)"`, `gemini-chat-transcript-prompts.md` Turn 06), `sky-high` (`gemini-apps-takeout-prompts.md` #277), `a shitload` (casual chat only, `gemini-chat-transcript-prompts.md` Turn 08).
- **Agent & runtime failure modes:** `spinning` (`5` uses, e.g., `"You're spending a lot of time spinning"`, `"It seems like you're spinning"`), `fall apart` (`"Without Mise, most of this will fall apart"`, `wishlist.md`), `step on its toes`, `leaking into` (`"I don't want anything leaking into the system-level"`, `gemini-apps-takeout-prompts.md` #366), `weird` (`"weird hard-to-reproduce errors"`, `"rendered weirdly"`).
- **Comparison & evaluation:** `stack up` (`"How's that stack up..."`, `gemini-apps-takeout-prompts.md` #108 and #142), `land` (`"Where's that land me?"`, #052 and #141), `end up` / `ended up` (`10` uses), `materially make a difference` (#249 and #254), `good enough` (#256), `don't need to get fancy` (#384).
- **Design & architecture:** `escape-hatches` (`junie-and-litellm-prompts.md` #221), `shore up` / `shoring up` (`junie-and-litellm-prompts.md` #282), `one-and-done` (`junie-and-litellm-prompts.md` #077), `stand up` (`"standing up the application"`, `"stand up the agent from scratch"`).

## 5. Explicit Documentation, Comment & Formatting Rules

Across the sessions, you gave explicit instructions about how documentation and summaries should be written. These are now encoded in [`junie/rules/personal-voice.md`](../../junie/rules/personal-voice.md):

- **Top-level vs. subsystem README hierarchy (`junie-and-litellm-prompts.md` #113, #334, #335, #345):**
  - Write for a human seeing the repository for the first time (`"geared towards a user running across the repo for the first time"`).
  - Keep top-level READMEs focused on **what** the repo/tools are for, **why** they exist, and **high-level how it works**. Strip low-level plumbing like exact websocket URLs, `sandbox-exec` internals, or bootstrap path mechanics (`~/bin/mise`).
  - Put deeper setup steps, prerequisites, architecture fit, and operational details into subsystem READMEs (`<system>/README.md`).
- **Brief, human-first docblocks (`junie-and-litellm-prompts.md` #010):** Keep explanatory docblocks to 1 to 2 short sentences (`"short and to the point, without being overly explanatory. A human will be reading this docblock."`).
- **Comment *why*, not *what* (`junie-and-litellm-prompts.md` #030):** Explicitly document *why* a workaround or disabled hook exists (`"We'll need to comment *why* we're disabling the listener and doing this."`).
- **Pre-run checklists & keeping docs accurate (`junie-and-litellm-prompts.md` #099, #112, #256, #272):** Put practical step-by-step checklists near the top when users need a specific run sequence, and delete obsolete steps as workflows evolve.
- **No emdashes anywhere (`junie-and-litellm-prompts.md` #286, #346):** Replace emdashes with commas, colons (`Label: content`), parentheses, or separate sentences. Do not use `--` as an emdash substitute.
- **Slack & Markdown rendering hygiene:**
  - Use `Label: content` colons on bullet points rather than dashes (`junie-and-litellm-prompts.md` #286).
  - Do not wrap link labels in backticks (`[task-dispatcher](url)`, never `` [`task-dispatcher`](url) ``), because Slack renders code-wrapped links poorly (`junie-and-litellm-prompts.md` #286).
  - Escape literal `$` currency figures in Markdown prose when renderers interpret pairs of `$...$` as LaTeX math (`\$1.00`, `junie-and-litellm-prompts.md` #111).

## 6. Anti-Patterns (What Breaks the Voice)

- **Emdashes (`U+2014`) or `--` prose stand-ins:** Immediately reads as unedited LLM output and violates `junie/rules/no-emdashes.md`.
- **Corporate/AI buzzwords:** Words like `leverage`, `seamless`, `robust`, `empower`, `comprehensive`, `cutting-edge`, `streamline`, `holistic`, or `orchestrate`.
- **Ceremonial intros and hype:** Openings like `"Welcome to..."`, `"In today's fast-paced..."`, `"This powerful tool..."`, promotional badges, or exclamation points.
- **Stiff uncontracted prose:** Writing `"it is"`, `"do not"`, `"does not"`, `"I am"`, or `"we are"` repeatedly in explanatory prose sounds robotic compared to your ~89% contraction rate.
- **Over-explaining obvious code or dumping internal plumbing at the top level:** Repeating CLI commands across sections or listing internal helper filenames and URLs in a project overview.

## 7. Voice Calibration Examples

### Top-Level README Overview

- **Generic AI prose:** "This comprehensive, declarative configuration framework leverages modular system manifests and lifecycle hooks to seamlessly provision and validate a robust macOS AI coding environment."
- **Target voice:** "This is my personal configuration repository for standing up and maintaining a local AI coding agent environment on macOS around JetBrains IDEs and Junie. I built it so I can bootstrap my setup from scratch on a fresh machine and verify that everything stays in sync over time."

### Technical Tradeoff Explanation

- **Generic AI prose:** "Rather than migrating to the `OpenAICompletion` endpoint (which would enable native `service_tier` support), we must retain the Google `:generateContent` API in order to seamlessly preserve critical subagent functionality."
- **Target voice:** "Switching `gemini-ladder` to `OpenAICompletion` breaks `spawn_subagent` because LiteLLM appends thought signatures to `tool_call.id`. Staying on the Google `:generateContent` API avoids that failure, though it means LiteLLM `1.111.0` ignores `reasoning_effort` and `service_tier` from `config.yaml` for now."

### Docblock / Code Comment

- **Generic AI prose:** "This listener method ensures that any buffered PostHog analytics events are reliably flushed during the Symfony kernel termination lifecycle phase, thereby preventing telemetry loss in the event of premature process exit."
- **Target voice:** "Flushes queued PostHog events after the HTTP response is sent. Skipping this drops events whenever a request finishes before the background batch buffer fills."

### Teammate Slack Update

- **Generic AI prose:** "**Checkpoint & Resume**: Added robust checkpointing capabilities to [`task-dispatcher`](https://github.com/estelsmith/llm-task-dispatcher) to seamlessly recover from partial runs!"
- **Target voice:** "- Checkpoint & Resume (PARTIAL Progress): Added workflow checkpointing to [task-dispatcher](https://github.com/estelsmith/llm-task-dispatcher) so interrupted runs can pick back up instead of starting over."

## 8. Applied Rule & Re-evaluation Workflow

- **Active rule file:** [`junie/rules/personal-voice.md`](../../junie/rules/personal-voice.md) now incorporates the full `799`-sample analysis (Junie, LiteLLM, Gemini Desktop transcript, and Google Takeout Gemini Apps). Run `bin/install junie` whenever you are ready to compile and deploy it into `~/.junie/AGENTS.md`.
- **Local prompt sample archive:** All `799` clean samples (`junie-and-litellm-prompts.md`, `gemini-chat-transcript-prompts.md`, and `gemini-apps-takeout-prompts.md`) plus `running-log.md` live locally under [`samples/`](./samples/README.md) and are excluded from Git via [`samples/.gitignore`](./samples/.gitignore).
- **Next refresh:** After appending new entries to `samples/running-log.md` locally, re-run the analysis against those samples whenever you want to refine `junie/rules/personal-voice.md`.
