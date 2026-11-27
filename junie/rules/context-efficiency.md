# Context & Turn Efficiency

Global conventions for keeping main-session context lean and minimizing redundant tool-call round-trips.

## Batch Parallel Reads & Searches

When inspecting multiple known files or running independent searches, issue them in parallel in a single turn instead of sequentially one file at a time.

## Delegate Noisy Exploration to Subagents

- **Broad or noisy discovery:** Delegate multi-file tracing, large log/config scans, or unfamiliar codebase exploration to a subagent and have it return a concise summary.
- **Small targeted lookups:** Keep 1 to 2 known file reads in the main session rather than spawning a subagent with an uncached prefix.
