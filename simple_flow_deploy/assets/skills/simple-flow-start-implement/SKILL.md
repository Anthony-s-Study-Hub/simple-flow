---
name: simple-flow-start-implement
description: Implement one approved file-backed Canonical Draft through a GitHub Issue and pull request.
---

# Simple Flow Start-Implement

Use this skill when the user asks to implement an approved Canonical Draft.

On Windows, use PowerShell-compatible Git and GitHub CLI commands; do not
assume Bash-only utilities are available.

## Select the draft

Read `.simple_tool/status.json` for the active draft. Use an explicit Draft ID
when the user supplied one. If neither identifies exactly one approved draft,
list the available `.simple_tool/drafts/DRAFT-*.json` files and ask the user to
choose; do not infer a proposal from conversation-only context.

Run this skill's bundled `scripts/select_path.py` with the selected Draft ID
and any applicable files from `.simple_tool/triage/`. Follow its result. A
`BLOCKED` result stops the workflow; do not publish an Issue or modify code.

## Implement through GitHub

1. Discover the repository and its default branch from the local `origin` and
   GitHub CLI. Use the default branch as the PR base (normally `main`); do not
   ask for values that are available locally.
2. Create or reuse the matching GitHub Issue. Its body must be the selected
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
