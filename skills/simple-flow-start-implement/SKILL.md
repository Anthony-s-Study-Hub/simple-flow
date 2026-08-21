---
name: simple-flow-start-implement
description: Start or continue formal Simple Flow implementation from an explicitly approved Draft ID and stop at human PR review.
---

# Simple Flow Start-Implement

Owned Stage: Start-Implement

Permission: publish-formal-issue

Human invocation must include an explicit Draft ID:

```text
Start-Implement <Draft ID>
```

The invocation means the named draft passed human review.

## Responsibilities

- Read exactly the specified Canonical Draft.
- Read the draft Work Type.
- Check whether current conversation context contains one clearly matching
  Review-Triage result.
- Choose the deterministic path.
- Publish or update the formal Issue only through the approved draft data.
- Create the bound branch and draft PR for formal implementation.
- For FEATURE, perform RED, implementation, GREEN, then wait for CI.
- For PROJECT_CHANGE, update only approved project documents and do not require
  TDD.
- Stop at Human PR Review.

## Boundaries

- Do not guess the latest Draft ID.
- Do not summarize a draft from chat.
- Do not edit an approved draft.
- Do not fill missing draft fields and continue.
- Do not guess when review-triage context is ambiguous.
- Do not merge pull requests.
- Do not invoke or simulate PR-Finalize.

Use deterministic helpers such as `simple_flow_agent.start_implement` for path
selection. Once the pull request is ready for human review, STOP.

