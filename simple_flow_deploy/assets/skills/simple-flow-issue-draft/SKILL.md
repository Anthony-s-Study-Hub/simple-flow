---
name: simple-flow-issue-draft
description: Turn an agreed change into a validated file-backed Canonical Draft without creating GitHub artifacts.
---

# Simple Flow Issue-Draft

Use this skill after discussion has produced an implementation-ready change, or
after Review-Triage has recorded a decision about an existing draft.

For this skill, explicit invocation is sufficient authorization. Create the
Canonical Draft without requesting a second confirmation.

## Outcome

Create exactly one Canonical Draft in `.simple_tool/drafts/`. It is the durable
handoff for later skills, even when the current conversation makes the intended
work clear.

## Execution

1. Read the current conversation to build the approved typed draft fields as
   JSON. FEATURE and DOCUMENTATION fields remain the source of truth for the
   eventual Issue body.
2. Run this skill's bundled `scripts/create_draft.py` from the directory that
   contains this `SKILL.md`. It writes the validated JSON and Markdown draft to
   `.simple_tool/drafts/` and uses `.simple_tool/roadmap-targets.txt`.
3. When a Review-Triage decision applies, pass its explicit
   `.simple_tool/triage/<decision-id>.json` file with `--triage-file`. Treat its
   resolution as authoritative: do not infer or replace the implementation
   route from chat. Preserve the decision ID and resulting route in the draft's
   execution metadata.
4. The script records the returned draft ID in `.simple_tool/status.json` when
   that installed state file exists. Report the draft ID and stop.

## Boundaries

- Do not create or edit a GitHub Issue, branch, pull request, or implementation change.
- Do not replace the file-backed draft with a chat-only summary.
- Do not invoke Start-Implement.
