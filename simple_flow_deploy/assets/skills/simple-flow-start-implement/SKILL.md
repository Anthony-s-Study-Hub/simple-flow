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

## Implement through GitHub

1. Discover the repository and its default branch from the local `origin` and
   GitHub CLI. Use the default branch as the PR base (normally `main`); do not
   ask for values that are available locally.
2. Create or reuse the matching GitHub Issue required by the plan. Its body must be the selected
   Canonical Draft's Markdown and preserve its acceptance criteria, scope, and
   out-of-scope limits.
3. Create a branch bound to that Issue, for example
   `feature/<issue-number>-<short-slug>`.
4. For a FEATURE, add a failing test when the project supports testing, make
   the smallest implementation that satisfies the draft, then run relevant
   tests. For DOCUMENTATION, run this skill's bundled
   `scripts/start_documentation.py` with the selected Draft ID.
5. Commit and push the change. Open a pull request against the default branch
   with `Closes #<issue-number>` in its body, the acceptance evidence, and the
   changed-file scope. Create it ready for review once tests pass; otherwise
   leave it as a draft and report the blocker.
6. Report the Issue and PR URLs, test results, and any remaining review work.
   Do not merge.

## Boundaries

- Do not create a new draft or rewrite the selected Canonical Draft.
- Do not create duplicate Issues for the same approved work.
- Do not merge; only PR-Finalize may merge after the user explicitly accepts
  the pull request.
