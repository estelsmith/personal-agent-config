# Personal Voice Prompt Samples

Clean, user-only prompt exports kept in a subdirectory so raw sample archives stay out of the way when browsing `research/personal-voice/`.

Because these exports contain personal chat history, [`samples/.gitignore`](./.gitignore) ignores `*.md` except for this `README.md` (`*.md` and `!README.md`). The four sample files below live only on local disk and are not committed to Git.

## Local Files (Gitignored)

| File | Contents | Count |
| --- | --- | --- |
| `junie-and-litellm-prompts.md` | Deduplicated user prompts from `~/.junie/sessions/` (`2026-11-18` through `2026-11-26`), `LiteLLM_SpendLogs` (`2026-11-26`), and follow-up turns in this session | 396 samples (82 Junie sessions + 3 LiteLLM-unique live turns) |
| `gemini-chat-transcript-prompts.md` | User turns extracted from `research/gemini-cost-reduction/gemini_chat_transcript.md` (`2026-11-26`) | 8 turns |
| `gemini-apps-takeout-prompts.md` | Deduplicated user turns from Google Takeout `MyActivity.html` (`2026-08-19` through `2026-11-26`, excluding the 8 turns already in `gemini-chat-transcript-prompts.md`) | 395 samples |
| `running-log.md` | Append-only file for new prompts, chat excerpts, or style feedback you want included in future rule revisions | Running log |

## Export & Sanitization Rules

To keep the sample corpus representative of your actual writing and safe to store in the repo, the exports apply these cleanup steps:

- **User words only:** Pasted AI responses (`>` and `- >` blockquotes), fenced code blocks, raw terminal command output, diff hunks, and JSON/stack-trace dumps were stripped.
- **Template removal:** Boilerplate expansions (such as `/task-dispatcher` prompt wrappers, automated code-review templates, subagent dispatch prompts, pasted AI handoff/profile blocks, and raw IDE error dumps) were excluded.
- **Deduplication:** Identical prompts repeated across retries, mirrored between `~/.junie/sessions/` and `LiteLLM_SpendLogs`, or already exported in `gemini-chat-transcript-prompts.md` were collapsed to a single entry.
- **Sensitive data redaction:** Third-party email addresses (`[redacted-email]`) and private medication, supplement, substance, and product/share URL references (`[redacted-medication]`, `[redacted-supplement]`, `[redacted-substance]`, `[redacted-provider]`, `[redacted-hormone]`, `[redacted-url]`) were replaced with placeholders while preserving sentence structure and phrasing.

## Re-evaluating `junie/skills/personal-voice/SKILL.md`

When you add entries to `running-log.md` locally, ask Junie to compare the new samples against [`../README.md`](../README.md) and update `junie/skills/personal-voice/SKILL.md` with any newly observed patterns, vocabulary, or register shifts.
