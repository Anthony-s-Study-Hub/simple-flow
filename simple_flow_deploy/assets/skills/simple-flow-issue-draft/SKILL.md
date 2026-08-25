---
name: simple-flow-issue-draft
description: Turn an agreed change into a validated file-backed Canonical Draft without creating GitHub artifacts.
---

# Simple Flow Issue-Draft

Use this skill after discussion has produced an implementation-ready change.

## Outcome

Create exactly one Canonical Draft in `.simple_tool/drafts/`. It is the durable
handoff for later skills, even when the current conversation makes the intended
work clear.

## Execution

1. Build the approved draft fields as JSON.
2. Run this skill's bundled `scripts/create_draft.py` from the directory that
   contains this `SKILL.md`. It writes the validated JSON and Markdown draft to
   `.simple_tool/drafts/` and uses `.simple_tool/roadmap-targets.txt`.
3. Record the returned draft ID in `.simple_tool/status.json` as the active
   draft, then report the draft ID and stop.

## Boundaries

- Do not create or edit a GitHub Issue, branch, pull request, or implementation change.
- Do not replace the file-backed draft with a chat-only summary.
