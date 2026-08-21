# Phase 2 Skills And Agent Policy

Phase 2 adds a soft-governance layer on top of the Phase 1 hard gates. It does
not replace CI, branch protection, issue validation, scope validation, or TDD
evidence checks.

## Artifacts

- `AGENTS.md` defines the shared Default Deny rules.
- `skills/simple-flow-discussion` owns discussion only.
- `skills/simple-flow-issue-draft` owns Canonical Draft creation only.
- `skills/simple-flow-start-implement` owns formal implementation startup and
  continuation only.
- `skills/simple-flow-review-triage` owns review finding classification only.
- `skills/simple-flow-pr-finalize` owns final merge authorization checks and
  cleanup only.
- `simple_flow_agent` contains deterministic helpers used by the skills and
  tests.
- `scripts/phase2_acceptance.py` runs the automatable acceptance scenarios.

## Deterministic Handoff

Issue-Draft stores each Canonical Draft as JSON and Markdown with a unique Draft
ID. Start-Implement must read the human-specified Draft ID and must not use the
latest draft as a substitute.

Review-Triage results remain conversation context. Start-Implement only consumes
a triage result when it clearly matches the draft source issue and PR. Ambiguous
review context stops the workflow.

PR-Finalize requires explicit human invocation. It checks objective merge
conditions and stops on failed CI, unresolved conversations, draft state, missing
PRs, closed PRs, or new commits after human review.

## Human Boundary

Automated tests cover deterministic behavior and connection rules. Human
semantic review is still required for deciding whether a draft is acceptable,
whether PR implementation is acceptable, and whether to invoke PR-Finalize.

