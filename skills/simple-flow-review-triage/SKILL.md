---
name: simple-flow-review-triage
description: Classify human PR review findings by relationship and merge impact without changing issues, branches, pull requests, or code.
---

# Simple Flow Review-Triage

Owned Stage: Review-Triage

Use this skill only after a human PR review identifies a finding.

## Responsibilities

Classify exactly two dimensions:

- Relationship: CURRENT, SUBISSUE, or NEW ISSUE.
- Merge Impact: BLOCKING or FOLLOW-UP.

The output must also include:

- Source Issue
- Source PR
- Reason

The result remains conversation context. It is not written to a state file.

## Execution

Run this skill's bundled classifier before outputting the triage result:

```powershell
python .codex/skills/review-triage/scripts/classify_finding.py --relationship <CURRENT|SUBISSUE|NEW ISSUE> --merge-impact <BLOCKING|FOLLOW-UP> --source-issue <issue-number> --source-pr <pr-number> --reason <reason>
```

Output the returned JSON fields in the conversation, then STOP. In this source
repository, the same bundled script lives at
`skills/simple-flow-review-triage/scripts/classify_finding.py`. Installed
projects use the `.codex/skills/review-triage/scripts/classify_finding.py` path
shown above.

## Boundaries

- Do not edit Issues.
- Do not modify code.
- Do not create branches or pull requests.
- Do not fix the finding directly.
- Do not invoke or simulate Issue-Draft.

After outputting the classification, STOP.

