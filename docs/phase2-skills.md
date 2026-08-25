# Phase 2 Skills And Agent Policy

Phase 2 adds a soft-governance layer on top of the Phase 1 hard gates. It does
not replace CI, branch protection, issue validation, scope validation, or TDD
evidence checks.

## Artifacts

- `AGENTS.md` defines the shared Default Deny rules.
- `simple_flow_deploy/assets/skills/simple-flow-discussion` owns discussion only.
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
- Start-Implement runs `scripts/select_path.py` before publishing Issues,
  creating branches, or changing files.
- PR-Finalize runs `scripts/check_pre_merge.py` before any merge.

Review-Triage results are saved under `.simple_tool/triage/`. Start-Implement
only consumes a triage result when it clearly matches the draft source issue
and PR. Ambiguous review context stops the workflow.

Review-Triage derives the finding, Source Issue, and Source PR from the current
conversation and repository context when one match is clear. Its classifier
still receives the resolved values explicitly; the user does not need to repeat
them.

PR-Finalize requires explicit human invocation. It checks objective merge
conditions and stops on failed CI, unresolved conversations, draft state, missing
PRs, closed PRs, or new commits after human review.

## Human Boundary

Automated tests cover deterministic behavior and connection rules. Human
semantic review is still required for deciding whether a draft is acceptable,
whether PR implementation is acceptable, and whether to invoke PR-Finalize.

