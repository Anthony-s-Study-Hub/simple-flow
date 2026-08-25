---
name: simple-flow-pr-finalize
description: Verify and merge an explicitly accepted pull request into the repository's default branch.
---

# Simple Flow PR-Finalize

Use this skill only when the user explicitly approves merging a pull request.

On Windows, use PowerShell-compatible Git and GitHub CLI commands; do not
assume Bash-only utilities are available.

## Select and verify the pull request

Use a PR number or URL supplied by the user. If none is supplied, infer the
single current PR from the conversation or checked-out branch. Ask for a choice
only when more than one plausible open PR exists.

Before merging, use GitHub CLI to confirm that the PR is open, targets the
repository's default branch, is not a draft, has completed required checks, and
has no unresolved review threads. If any condition fails, report it and stop.

## Merge route

Merge with the repository's normal merge method into its default branch
(normally `main`), close the linked Issue through the PR's `Closes #...` link,
and delete the head branch when repository policy permits. Report the merge URL
and final status.

## Boundaries

- Do not treat an ordinary "looks good" comment as merge authorization.
- Do not force merge, bypass protection, resolve reviews automatically, or fix
  failing checks.
- Do not merge an ambiguous or unreviewed PR.
