---
name: simple-flow-documentation-curation
description: Turn project history into a validated file-backed documentation Canonical Draft without modifying project content.
---

# Simple Flow Documentation-Curation

Use this skill when the user wants to turn Issue, PR, review, and merge history
into a future documentation change.

On Windows, use PowerShell-compatible commands when collecting local history.

## Outcome

Analyze the supplied or locally available history and run this skill's bundled
`scripts/curate_documentation.py`. It records its deterministic curation output
under `.simple_tool/documentation-curation/` and creates a DOCUMENTATION
Canonical Draft in `.simple_tool/drafts/`. Identify durable decisions,
conflicts, superseded guidance, affected documents, and proposed edits. Mark
uncertain evidence as an open question rather than inventing a conclusion.

Report the Draft ID and stop. A later Start-Implement invocation uses that
file-backed draft.

## Boundaries

- Do not modify documentation, Issues, branches, or pull requests.
- Do not create an Issue, branch, pull request, or project-content change.
- Do not merge.
