# Junie Global Rules & Skills

This system compiles my modular Markdown rule files under `junie/rules/` into Junie's global instructions file (`~/.junie/AGENTS.md`), syncs Junie-owned skills via `junie/manifest` (like `personal-voice`), and makes sure the installed copies stay in sync.

## Why I Use It

Rather than editing one large `~/.junie/AGENTS.md` file by hand, I keep unrelated conventions in small, focused files under `junie/rules/` (such as terminal command intent, preferring Docmancer over guessing APIs, and avoiding emdashes). Those rules apply across every Junie session and repository.

Because `hooks/post-install` renders `~/.junie/AGENTS.md` deterministically in sorted filename order and `hooks/doctor` verifies its SHA-256 digest and permissions (`0644`), accidental manual edits or stray symlinks get caught right away.

## How It Fits In

`~/.junie/AGENTS.md` sets my always-on behavioral baseline across projects, while on-demand skills (`~/.junie/skills/personal-voice/SKILL.md` from this system and [`docmancer`](../docmancer/README.md)'s `~/.junie/skills/docmancer/SKILL.md`) only load when a task calls for them. Inside [`safehouse`](../safehouse/README.md), `junie-safehouse` mounts `~/.junie` read/write so Junie can read `AGENTS.md`, skills, and session state normally.

### Custom Models (`~/.junie/models/`)

Custom Gemini model profiles in `~/.junie/models/` (such as `gemini-ladder.json` and `litellm-gemini-4-hydrogen-*.json`, currently managed outside `junie/manifest`) **must use `apiType: "Google"`** (`:generateContent`) rather than `apiType: "OpenAICompletion"`.

- Via LiteLLM's OpenAI chat endpoint (`OpenAICompletion`), `embeds_thought_signature_in_tool_call_id` defaults to `True`, appending a long `__thought__<base64_signature>` suffix onto `tool_call.id`. That breaks Junie's `spawn_subagent` tool calls (used by `/task-dispatcher`), and moving signatures to non-standard fields fails when tool-result echoes strip them.
- Using `apiType: "Google"` (`:generateContent`) keeps Gemini's `thoughtSignature` natively inside `content.parts[]`, so subagent spawning works reliably. [`litellm-proxy/custom_callbacks.py`](../litellm-proxy/custom_callbacks.py) patches `GoogleGenAIGenerateContentHandler.get_structured_messages` specifically so `complexity_router` (`gemini-ladder`) works with `:generateContent` payloads.

## How It Works

`junie/manifest` syncs static files and skills directly into `~/.junie/` (currently `skills/personal-voice/SKILL.md` -> `~/.junie/skills/personal-voice/SKILL.md`), while `~/.junie/AGENTS.md` is generated dynamically by hooks:

1. `junie/hooks/_junie.py` collects every non-empty `*.md` file in `junie/rules/` sorted by filename, normalizes line endings, and joins them with blank lines (`\n\n`).
2. `junie/hooks/post-install` atomically writes the rendered output to `~/.junie/AGENTS.md` (`0644`) whenever the file is missing, is a symlink, or differs in SHA-256 hash or mode.
3. `junie/hooks/doctor` re-renders `junie/rules/*.md` in memory and verifies that `~/.junie/AGENTS.md` is a regular file with the exact expected SHA-256 digest and `0644` permissions.

## Quick Start

```bash
# Sync junie skills/manifest files, render junie/rules/*.md, and update ~/.junie/AGENTS.md
bin/install junie

# Verify ~/.junie/skills/* and ~/.junie/AGENTS.md match the repo
bin/doctor junie
```

## Files & Hooks

| Path | Role | Details |
| --- | --- | --- |
| `junie/rules/*.md` | Source rules | Modular Markdown rule files concatenated in sorted filename order (e.g., `bash-command-intent.md`, `docmancer-first.md`). |
| `junie/skills/personal-voice/SKILL.md` | On-demand skill | Callable `personal-voice` skill synced to `~/.junie/skills/personal-voice/SKILL.md` for writing docs in my voice when requested. |
| `junie/manifest` | Static files & skills | Maps static `~/.junie/` files and skills (`0644 skills/personal-voice/SKILL.md ~/.junie/skills/personal-voice/SKILL.md`). |
| `junie/hooks/post-install` | Build and sync hook | Renders `junie/rules/*.md` into `~/.junie/AGENTS.md` (`0644`). |
| `junie/hooks/doctor` | Health check hook | Verifies `~/.junie/AGENTS.md` exists as a regular file with matching SHA-256 and `0644` mode. |
| `junie/hooks/_junie.py` | Shared helper module | Rule discovery, deterministic rendering, atomic writes, and SHA-256/mode checks. |
