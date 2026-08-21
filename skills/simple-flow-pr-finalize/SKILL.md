---
name: simple-flow-pr-finalize
description: Perform deterministic pre-merge checks and cleanup verification after explicit human acceptance of a Simple Flow pull request.
---

# Simple Flow PR-Finalize

Owned Stage: PR-Finalize

Permission: merge-pull-request

Human invocation must name a pull request:

```text
PR-Finalize <PR>
```

The invocation is the semantic human authorization that the current PR
implementation has been reviewed and accepted.

## Responsibilities

- Confirm the pull request exists and is open.
- Confirm the pull request is not draft, or apply the fixed ready conversion
  rule before merging.
- Confirm required CI checks passed.
- Confirm there are no unresolved review conversations.
- Confirm there are no new commits after human review that require fresh
  confirmation.
- Merge only after objective checks pass.
- Confirm linked Issue closure.
- Confirm head branch deletion.
- Confirm GitHub Projects status cleanup.
- Output the result and STOP.

## Boundaries

- Do not run a new intelligent code review.
- Do not replace human judgment.
- Do not edit business code.
- Do not fix CI failures.
- Do not resolve review conversations automatically.
- Do not force merge or use admin bypass when checks fail.

Any failed precondition is a blocker: report the exact condition and STOP.

