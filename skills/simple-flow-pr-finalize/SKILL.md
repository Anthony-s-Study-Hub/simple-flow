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

## Execution

1. Confirm the human explicitly invoked `PR-Finalize <PR>`.
2. Collect objective PR state from GitHub and CI into a JSON file with these
   fields: `exists`, `open`, `draft`, `required_checks`,
   `unresolved_conversations`, `commits_after_human_review`,
   `linked_issue_closed`, `head_branch_deleted`, and `project_item_updated`.
3. Run this skill's bundled pre-merge script before merging:

```powershell
python .codex/skills/pr-finalize/scripts/check_pre_merge.py --state <pr-state.json> --authorized
```

4. If the script exits nonzero, report the exact blocker and STOP.
5. Only after a successful script result, perform the merge and required cleanup
   confirmations, then output the result and STOP.

In this source repository, the same bundled script lives at
`skills/simple-flow-pr-finalize/scripts/check_pre_merge.py`. Installed projects
use the `.codex/skills/pr-finalize/scripts/check_pre_merge.py` path shown above.

## Boundaries

- Do not run a new intelligent code review.
- Do not replace human judgment.
- Do not edit business code.
- Do not fix CI failures.
- Do not resolve review conversations automatically.
- Do not force merge or use admin bypass when checks fail.

Any failed precondition is a blocker: report the exact condition and STOP.

