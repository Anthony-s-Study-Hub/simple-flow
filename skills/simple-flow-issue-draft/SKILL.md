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

- Build one structured Canonical Draft for either FEATURE or PROJECT_CHANGE.
- Validate the draft with deterministic draft and issue-contract logic.
- Assign a unique Draft ID.
- Save structured JSON and render human-readable Markdown from the same data.
- Output the Draft ID and STOP.

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
PROJECT_CHANGE_REQUIRED. Do not create a new roadmap target.

## PROJECT_CHANGE Contract

- Type
- Change
- Reason
- Impact
- Supersedes
- Affected Project Documents
- Source PR / Decision Context

## Boundaries

- Do not publish GitHub Issues.
- Do not create branches or pull requests.
- Do not modify implementation code.
- Do not invoke or simulate Start-Implement.

Mechanics should use `simple_flow_agent.drafts.DraftStore` or an equivalent
deterministic helper. After reporting the Draft ID, STOP.

