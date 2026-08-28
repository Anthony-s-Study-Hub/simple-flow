---
name: simple-flow-pr-finalize
description: Verify and merge an explicitly accepted pull request into the repository's default branch.
---

# Simple Flow PR-Finalize

Use this skill only when the user explicitly approves merging a pull request.

On Windows, use PowerShell-compatible Git and GitHub CLI commands; do not
assume Bash-only utilities are available.

## Verify and merge the real pull request

Use the PR number or URL explicitly accepted by the user. Run this skill's
bundled `scripts/finalize_remote_pr.py` with that PR, the repository, and its
explicit approval flag. The script reads live GitHub state: the default branch,
open and non-draft PR state, required checks, and unresolved review threads.
It fails closed on any blocker, then merges with the repository's normal GitHub
route and verifies the merge remotely.

## Boundaries

- Do not treat an ordinary "looks good" comment as merge authorization.
- Do not force merge, bypass protection, resolve reviews automatically, or fix
  failing checks.
- Do not merge an ambiguous or unreviewed PR.
