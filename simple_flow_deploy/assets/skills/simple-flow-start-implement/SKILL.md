---
name: simple-flow-start-implement
description: Implement one approved file-backed Canonical Draft through a GitHub Issue and pull request.
---

# Simple Flow Start-Implement

Use this skill when the user asks to implement an approved Canonical Draft.

On Windows, use PowerShell-compatible Git and GitHub CLI commands; do not
assume Bash-only utilities are available.

## Plan deterministically

Translate the user's implementation request into a small intent JSON with
`tags`, `components`, and optional `terms`. These are agent reasoning inputs,
not workflow decisions. Run this skill's bundled
`scripts/plan_implementation.py` with that JSON, `.simple_tool/status.json`,
and the installed `.simple_tool/drafts/` records.

The planner selects from eligible drafts using an explicit Draft ID first, then
structured intent evidence, then durable active state. Do not ask merely
because several drafts exist. Follow its selected Draft ID, route, constraints,
and required actions exactly. If the planner reports `blocked`, stop and report
its structured reason; do not publish an Issue or modify code.

For a review-derived draft, its stored implementation route is authoritative.
Do not re-read chat or raw triage justification to decide whether to revise,
create a subissue, create independent work, or update a current PR.

## Deliver through GitHub

Save the ready planner JSON, discover the repository and default branch from
`origin`, then run `scripts/delivery_pr.py open`. This is the only entrypoint
that creates or reuses the planned Issue, its bound branch, and its draft PR.
It persists an idempotent delivery record in `.simple_tool/deliveries/`.

The draft PR must exist before implementation begins. For a FEATURE, make a
focused failing-test commit, the smallest implementation commit, then a GREEN
commit with the TDD evidence required by the repository. For DOCUMENTATION,
make the approved documentation change and run its relevant checks. Do not
change the selected Draft or invent a second delivery route.

After pushing the completed work, run `scripts/delivery_pr.py ready`. It reads
live GitHub state, fails closed until every required check passes, marks the PR
ready for review, and verifies the CI run triggered by that transition. Report
the Issue and PR URLs, test results, and remaining human review work. Do not
merge.

## Boundaries

- Do not create a new draft or rewrite the selected Canonical Draft.
- Do not create duplicate Issues for the same approved work.
- Do not merge; only PR-Finalize may merge after the user explicitly accepts
  the pull request.
