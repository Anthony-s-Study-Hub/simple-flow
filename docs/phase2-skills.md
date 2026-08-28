# Phase 2 Skills And Agent Policy

Phase 2 adds a soft-governance layer on top of the Phase 1 hard gates. It does
not replace CI, branch protection, issue validation, scope validation, or TDD
evidence checks.

## Artifacts

- `AGENTS.md` defines the shared Default Deny rules.
- `simple_flow_deploy/assets/skills/simple-flow-issue-draft` owns Canonical Draft creation only.
- `simple_flow_deploy/assets/skills/simple-flow-start-implement` owns formal implementation startup and
  continuation only.
- `simple_flow_deploy/assets/skills/simple-flow-review-triage` owns review finding classification only.
- `simple_flow_deploy/assets/skills/simple-flow-pr-finalize` owns final merge authorization checks and
  cleanup only.
- Each executable skill owns a `scripts/` entrypoint under its skill folder.
- `simple_flow_agent` contains shared deterministic helper code used by those
  skill-local scripts and tests.
- `scripts/phase2_acceptance.py` runs the automatable acceptance scenarios.

## Deterministic Handoff

Issue-Draft stores each Canonical Draft as JSON and Markdown under
`.simple_tool/drafts/` with a unique Draft ID. Start-Implement reads the active
draft from `.simple_tool/status.json`, or uses an explicit Draft ID when
supplied, then reads that exact draft from disk. It asks for a Draft ID only
when neither source identifies exactly one approved draft.

The stage scripts are the deterministic handoff points:

- Issue-Draft runs `scripts/create_draft.py` before reporting a Draft ID.
- Review-Triage runs `scripts/classify_finding.py` before outputting a
  classification.
- Start-Implement runs `scripts/plan_implementation.py`, then its
  `scripts/delivery_pr.py` entrypoint before implementation or review readiness.
- PR-Finalize runs `scripts/finalize_remote_pr.py` before any merge.

Review-Triage results are saved under `.simple_tool/triage/`. Issue-Draft
consumes a selected decision to create the successor Draft; Start-Implement
consumes only that routed Draft. `.simple_tool/` transition files may be
written only by their owning skills.

## Deterministic Implementation Planning

Issue-Draft preserves the typed FEATURE or DOCUMENTATION fields used to render
the Issue body, and stores execution metadata only in the canonical JSON. That
metadata includes intent tags, components, lifecycle, priority, and an explicit
implementation route. Review-Triage decisions may set a route for a successor,
child, independent, or current-PR draft.

Start-Implement converts the user's request into structured intent inputs, then
runs `scripts/plan_implementation.py`. The planner selects an eligible draft by
explicit ID, structured intent evidence, or durable active state and records
why it selected that draft. Multiple drafts alone do not require a question; a
material tie or invalid structured state stops safely. The agent performs the
semantic work of writing FEATURE code or non-mechanical documentation, while
the plan fixes the route, scope constraints, TDD requirement, and publication
actions. Start-Implement opens or reuses the Issue, branch, and draft PR
through one idempotent delivery record; it leaves the PR review-ready only
after the live required CI checks pass.

Review-Triage derives the finding, Source Issue, and Source PR from the current
conversation and repository context when one match is clear. Its classifier
still receives the resolved values explicitly; the user does not need to repeat
them.

PR-Finalize requires explicit human invocation. It queries GitHub directly,
stops on failed CI, unresolved conversations, draft state, missing PRs, or
closed PRs, and performs the normal remote merge only after those checks pass.

## Human Boundary

Automated tests cover deterministic behavior and connection rules. Human
semantic review is still required for deciding whether a draft is acceptable,
whether PR implementation is acceptable, and whether to invoke PR-Finalize.

