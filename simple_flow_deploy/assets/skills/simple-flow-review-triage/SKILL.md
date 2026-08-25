---
name: simple-flow-review-triage
description: Classify a human pull-request review finding into a durable local handoff without changing project or GitHub artifacts.
---

# Simple Flow Review-Triage

Use this skill after a human PR review identifies a finding.

Classify the finding in the conversation as one of:

- CURRENT, SUBISSUE, or NEW ISSUE
- BLOCKING or FOLLOW-UP

Include the source Issue and PR when known, a short reason, and the recommended
next step. Run this skill's bundled `scripts/classify_finding.py`, save its JSON
output in `.simple_tool/triage/`, and report that file path. Start-Implement
uses the file as input when the user asks for follow-up implementation.

## Boundaries

- Do not modify Issues, code, branches, pull requests, or review threads.
- Do not modify drafts, Issues, code, branches, pull requests, or review threads.
- Do not merge.
