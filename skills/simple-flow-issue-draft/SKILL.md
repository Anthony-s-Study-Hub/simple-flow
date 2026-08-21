---
name: simple-flow-issue-draft
description: Convert mature Simple Flow discussion into a validated Canonical Draft and stop before GitHub Issue creation or implementation.
---

# Simple Flow Issue-Draft

Owned Stage: Issue-Draft

Permission: generate-canonical-draft

Use this skill only after discussion is mature enough to define what should
change.

## Responsibilities

- Build one structured Canonical Draft for either FEATURE or DOCUMENTATION.
- Validate the draft with deterministic draft and issue-contract logic.
- Assign a unique Draft ID.
- Save structured JSON and render human-readable Markdown from the same data
  under `.simple-flow/drafts/`.
- Output the Draft ID and STOP.

## Execution

1. Prepare a JSON input file containing the approved draft fields.
2. Run this skill's bundled script before reporting a Draft ID:

```powershell
python .codex/skills/issue-draft/scripts/create_draft.py --input <draft-input.json> --drafts-dir .simple-flow/drafts --roadmap-targets .simple-flow/roadmap-targets.txt
```

3. Use only the script output as the Canonical Draft handoff.
4. Report the returned `draft_id`, `json_path`, and `markdown_path`, then STOP.

In this source repository, the deploy-time script source of truth is
`simple_flow_deploy/skill_resources/issue-draft/scripts/create_draft.py`.
Installed projects use the `.codex/skills/issue-draft/scripts/create_draft.py`
path shown above.

## FEATURE Contract

- Type
- Summary
- Requirements
- Acceptance Criteria
- Scope
- Out of Scope
- Documentation Impact
- Roadmap Target

Roadmap Target must be an existing target, UNMAPPED, or
DOCUMENTATION_REQUIRED. Do not create a new roadmap target.

## DOCUMENTATION Contract

- Type
- Change
- Reason
- Impact
- Supersedes
- Affected Project Documents
- Source PR / Decision Context

Legacy `PROJECT_CHANGE` input is accepted only as an alias for DOCUMENTATION
during migration. New drafts must use DOCUMENTATION.

## Boundaries

- Do not publish GitHub Issues.
- Do not create branches or pull requests.
- Do not modify implementation code.
- Do not invoke or simulate Start-Implement.

Mechanics must use the bundled `scripts/create_draft.py` entrypoint. After
reporting the Draft ID, STOP. The entrypoint writes the Canonical Draft JSON
and Markdown under `.simple-flow/drafts/`.

