---
name: simple-flow-documentation-curation
description: Turn project history into a reviewable documentation-change proposal without modifying the project.
---

# Simple Flow Documentation-Curation

Use this skill when the user wants to turn Issue, PR, review, and merge history
into a future documentation change.

On Windows, use PowerShell-compatible commands when collecting local history.

## Outcome

Analyze the supplied or locally available history and produce one
documentation-ready proposal in the conversation. Identify durable decisions,
conflicts, superseded guidance, affected documents, and proposed edits. Mark
uncertain evidence as an open question rather than inventing a conclusion.

The proposal can be handed to Issue-Draft or implemented directly when the
user clearly approves it. Do not persist curation state in the target project.

## Boundaries

- Do not modify documentation, Issues, branches, or pull requests.
- Do not create a hidden cursor, baseline, draft, or other project artifact.
- Do not merge.
