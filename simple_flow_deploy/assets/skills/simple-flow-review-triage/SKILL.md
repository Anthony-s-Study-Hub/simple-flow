---
name: simple-flow-review-triage
description: Classify a draft-stage change or human pull-request review finding into a durable, explicit routing decision.
---

# Simple Flow Review-Triage

Use this skill after either a new request changes an unimplemented Canonical
Draft or a human PR review identifies a finding.

For this skill, explicit invocation is sufficient authorization. Record its
decision without requesting a second confirmation.

Classify the finding in the conversation as one of:

- CURRENT, SUBISSUE, or NEW ISSUE
- BLOCKING or FOLLOW-UP

Create one decision with a relationship (`CURRENT`, `SUBISSUE`, or `NEW ISSUE`)
and an explicit resolution. For a draft-stage decision, identify the target
Draft ID and choose one of `SUPERSEDE_DRAFT`, `CREATE_CHILD_DRAFT`, or
`CREATE_INDEPENDENT_DRAFT`. For a delivery-stage decision, include the source
Issue and PR and choose `PATCH_CURRENT_PR`, `CREATE_LINKED_FOLLOW_UP`, or
`CREATE_INDEPENDENT_FOLLOW_UP`.

Run this skill's bundled `scripts/classify_finding.py` with a durable decision
ID and `--output .simple_tool/triage/<decision-id>.json`. Report that file path
and stop. Do not invoke Issue-Draft; a later Issue-Draft invocation consumes the
selected decision and the current conversation.

## Boundaries

- Do not modify drafts, Issues, code, branches, pull requests, or review threads.
- Do not merge.
