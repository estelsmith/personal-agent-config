# External Code & Library Lookup Rules

Global conventions for looking up documentation, APIs, and behavior of applications, frameworks, SDKs, or libraries outside the repository root.

## Always Consult Docmancer First

Although `docmancer` is provided as an Agent Skill, using it is **mandatory**, not optional. Whenever you need to look up code, APIs, configuration, or behavior in applications or libraries outside of the repository root (such as installed packages, `site-packages`, `node_modules`, vendor directories, or external repositories):

- **Consult Docmancer first**: Read the `docmancer` skill and query indexed documentation strictly via `mise exec -- docmancer docs query` (do not use `docmancer ask`, which searches Shared Memory) before reading or searching external source files.
- **Check and index missing sources**: Run `mise exec -- docmancer docs list` to see available sources, and index missing documentation with `mise exec -- docmancer docs add` when official docs or a local docs directory/repo are available.
- **Fall back to third-party codebases only if Docmancer is insufficient**: You may search or read third-party codebases outside the repository root **only after** consulting Docmancer proves insufficient (for example, when Docmancer returns no relevant coverage, cannot index the source, or does not answer the specific internal implementation detail needed).
