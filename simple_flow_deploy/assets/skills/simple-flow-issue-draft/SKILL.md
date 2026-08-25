---
name: simple-flow-issue-draft
description: Turn a mature project discussion into one issue-ready implementation proposal without creating GitHub artifacts.
---

# Simple Flow Issue-Draft

Use this skill when the conversation has converged on a change but the user has
not yet asked to implement it.

## Outcome

Produce one concise, issue-ready proposal in the conversation. It must include:

- title and work type (FEATURE or DOCUMENTATION)
- problem and intended outcome
- requirements and acceptance criteria
- scope and explicit out-of-scope items
- affected files or documentation, when known

Treat the proposal as the current conversation's implementation handoff. Do
not write it to a project state directory or require a Draft ID.

## Boundaries

- Do not create or edit a GitHub Issue.
- Do not create a branch, pull request, or implementation change.
- Do not invent missing product decisions; mark them as open questions.

When the proposal is complete, ask the user to approve implementation. A later
clear instruction such as "implement this" is sufficient to let
Start-Implement use this proposal; an explicit identifier is not required.
