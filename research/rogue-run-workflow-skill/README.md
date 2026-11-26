# Rogue `skills/system/run-workflow/SKILL.md` Investigation

Investigation notes on the unexpected `skills/system/run-workflow/SKILL.md` directory and file written into `personal-agent-config` (and likely other repositories) by Antigravity after installing it as a PhpStorm agent.

---

## 1. Summary

- **Observed artifact:** Untracked directory tree `skills/system/run-workflow/SKILL.md` created inside `~/repositories/personal/personal-agent-config` without user request.
- **Origin confirmed by user:** Antigravity, recently installed as a PhpStorm agent.
- **Ruled out:** Junie did not create this file. Junie session logs, process start times, and skill conventions all eliminate Junie as the writer.
- **Why this note exists:** This session ran inside `junie-safehouse`, which restricts read access outside `personal-agent-config` (blocking `~/.gemini`, PhpStorm logs, and sibling repositories under `~/repositories/`). A follow-up session running outside safehouse can use the fingerprints and checklist below to find and clean up every repo and directory Antigravity touched.

---

## 2. Artifact Details & Fingerprints

### Filesystem Metadata (`personal-agent-config`)

- **Paths created (all untracked in git):**
  - `skills/` (mode `0755`, birth/mtime `2026-11-26 16:33:18`)
  - `skills/system/` (mode `0755`, birth/mtime `2026-11-26 16:33:18`)
  - `skills/system/run-workflow/` (mode `0755`, birth/mtime `2026-11-26 16:33:18`)
  - `skills/system/run-workflow/SKILL.md` (mode `0644`, birth/mtime `2026-11-26 16:33:18`, size `10331` bytes)
- **SHA-256:** `82ed7c2e93d79fd95a01188c78539b6987f4c2a2dfc49c3b8991bebbe8925bf`
- **Git status:** `?? skills/system/run-workflow/SKILL.md`

### Content & Format Signatures

The frontmatter and body of `skills/system/run-workflow/SKILL.md` match Google Gemini / Antigravity orchestration primitives rather than Junie:

- **Frontmatter:**
  - `name: run-workflow`
  - `metadata.namespace: system`
  - Mentions `migrate-workflows` ("or for legacy workflow files (see migrate-workflows)")
- **Tool and schema identifiers:**
  - `run_workflow` tool with parameters `Script`, `ScriptPath`, `Description`, `WaitMsBeforeAsync`, `Args`, `Cwd`
  - Python script primitives: `log()`, `phase()`, `agent()`, `parallel()`, `pipeline()`, `trajectory()`, `call_tool()`, `ToolError`, `CONVERSATION_ID`, `STEP_INDEX`, `WORKSPACES`
  - Model tiers: `"inherit"`, `"flash_lite"`, `"flash"`, `"pro"`
  - Step types: `"USER_INPUT"`, `"PLANNER_RESPONSE"`, `"SYSTEM_MESSAGE"`, `"GENERIC"`
  - Conversation artifacts referenced: `workflow.json`, `transcript.jsonl`, `transcript_full.jsonl`, `finish` tool

---

## 3. Evidence Ruling Out Junie

1. **Timeline mismatch against Junie ACP processes:**
   - The preceding `personal-agent-config` Junie session (`session-261126-135420-59g5`, PID `22710`) finished active work at `15:52:05` (with only a settings refresh at `16:09:28`) and received no further prompt until `16:42:42`.
   - The next `personal-agent-config` Junie session (`session-261126-163320-1x62`, PID `47752`) did not start its `junie` ACP process until `16:33:20.134` (two seconds *after* `SKILL.md` was already on disk at `16:33:18`), and did not receive a user prompt until `16:37:35`.
2. **Zero matches in Junie history:**
   - Searching `~/.junie/sessions/` (`transcript.md`, `events.jsonl`, `subagents/`) and `~/.junie/logs/` showed no mentions of `run-workflow`, `run_workflow`, `skills/system`, `WaitMsBeforeAsync`, or `PLANNER_RESPONSE` prior to `16:41` (when `session-261126-164123-1cec/state.json` recorded the project directory listing after the file already existed).
3. **Different skill layout:**
   - Junie's built-in skills live under `~/.junie/versions/<version>/skills/` (`demo-setup`, `junie-cross-review`, `session-history`), and personal/global Junie skills in this setup live under `~/.junie/skills/` (deployed from `docmancer/skills/`), not `<repo>/skills/system/`.

---

## 4. Sandbox Restrictions Observed

Inside `junie-safehouse`, attempts to inspect external locations returned `Operation not permitted`:

- `~/.gemini`
- `~/Library/Logs/JetBrains/PhpStorm2026.2/`
- `/Applications/Gemini.app`
- Other repositories under `~/repositories/` outside the current working repository (`personal-agent-config`)

---

## 5. Follow-Up Checklist for Unsandboxed Session

Run these checks in an unsandboxed session with access to `~/repositories/`, `~/`, and PhpStorm/Antigravity directories:

1. **Scan `~/repositories/` for `skills/system` or matching `SKILL.md` files:**
   - Check for any `skills/system` directories, `run-workflow/SKILL.md`, or `migrate-workflows` references across all repositories in `~/repositories/`.
   - Check file hashes against `82ed7c2e93d79fd95a01188c78539b6987f4c2a2dfc49c3b8991bebbe8925bf` and timestamps around `2026-11-26 16:33` (or whenever PhpStorm/Antigravity opened each project).
   - Check `git status` in every affected repository to verify whether `skills/` or other Antigravity artifacts (e.g., `.agent/`, `.gemini/`, `workflow.json`, `transcript*.jsonl`) are untracked or modified tracked files.
   - Example search commands:
     ```bash
     find ~/repositories -maxdepth 5 -path '*/skills/system*' -o -name 'run-workflow'
     find ~/repositories -name 'SKILL.md' -exec shasum -a 256 {} +
     find ~/repositories -maxdepth 4 \( -name '.agent' -o -name '.gemini' -o -name 'skills' \)
     ```
2. **Inspect Antigravity / PhpStorm configuration and logs:**
   - Check `~/Library/Logs/JetBrains/PhpStorm2026.2/` and PhpStorm ACP/agent configuration under `~/Library/Application Support/JetBrains/PhpStorm2026.2/` for Antigravity workspace seeding behavior.
   - Check `~/.gemini` (and any Antigravity application support/config directories) to see why it auto-seeds `skills/system/run-workflow/SKILL.md` into workspace roots and whether that behavior can be disabled or pointed elsewhere.
3. **Clean up:**
   - Remove `skills/` from `personal-agent-config` (and any other affected repositories under `~/repositories/`) once the scan and root-cause check are complete.
   - Remove `research/rogue-run-workflow-skill/` afterwards if these notes are no longer needed.
