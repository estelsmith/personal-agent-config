# Junie Global Rules & Skills

This system compiles my rule files under `junie/rules/` into Junie's global instructions (`~/.junie/AGENTS.md`) and syncs Junie-owned skills (like `personal-voice`).

## Why I Use It

Rather than editing one large `~/.junie/AGENTS.md` file by hand, I keep unrelated conventions in small, focused files under `junie/rules/` (like terminal command intent, checking Docmancer first, and skipping emdashes). Those rules apply across every Junie session and repo, and `bin/doctor junie` catches accidental local edits or stray symlinks right away.

## How It Fits In

- **Always-on rules:** `~/.junie/AGENTS.md` sets my baseline conventions across projects.
- **On-demand skills:** Skills like `personal-voice` (here) and `docmancer` (from [`docmancer`](../docmancer/README.md)) only load into context when a task asks for them.
- **Sandboxed access:** Inside [`safehouse`](../safehouse/README.md), `~/.junie` stays read/write so Junie can read `AGENTS.md`, skills, and session state normally.

## How It Works

Static files and skills sync through `junie/manifest`, while `~/.junie/AGENTS.md` is built on install by stitching every non-empty `*.md` file in `junie/rules/` together in alphabetical order. Simple is better.

### Custom Gemini Models (`~/.junie/models/`)

If you add custom Gemini profiles under `~/.junie/models/` (like `gemini-ladder.json` and `litellm-gemini-4-hydrogen-*.json`, currently managed outside this repo), set `apiType: "Google"` instead of `OpenAICompletion`. LiteLLM's OpenAI chat endpoint tacks thought signatures onto tool call IDs, which breaks Junie's subagent spawning (`/task-dispatcher`). Keeping `apiType: "Google"` avoids that, and [`litellm-proxy`](../litellm-proxy/README.md) patches both complexity routing and `reasoning_effort` (`thinkingConfig`) propagation for native Google payloads.

## Quick Start

```bash
# Sync skills and compile junie/rules/*.md into ~/.junie/AGENTS.md
bin/install junie

# Verify installed skills and compiled AGENTS.md match the repo
bin/doctor junie
```

## Files

| Path | What It Is For |
| --- | --- |
| `junie/rules/*.md` | Modular rule files stitched alphabetically into `~/.junie/AGENTS.md`. |
| `junie/skills/personal-voice/SKILL.md` | On-demand skill for writing docs in my voice when requested. |
| `junie/manifest` | Maps static files and skills into `~/.junie/`. |
| `junie/hooks/post-install` | Compiles `junie/rules/*.md` into `~/.junie/AGENTS.md`. |
| `junie/hooks/doctor` | Checks that `~/.junie/AGENTS.md` matches the compiled rules. |
