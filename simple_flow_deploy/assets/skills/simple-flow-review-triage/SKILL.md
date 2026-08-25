---
name: simple-flow-review-triage
description: Classify a human pull-request review finding without changing project or GitHub artifacts.
---

# Simple Flow Review-Triage

Use this skill after a human PR review identifies a finding.

Classify the finding in the conversation as one of:

- CURRENT, SUBISSUE, or NEW ISSUE
- BLOCKING or FOLLOW-UP

Include the source Issue and PR when known, a short reason, and the recommended
next step. Keep the result in conversation context so Start-Implement can use
it when the user asks for follow-up implementation.

## Boundaries

- Do not modify Issues, code, branches, pull requests, or review threads.
- Do not create project-local state files.
- Do not merge.
