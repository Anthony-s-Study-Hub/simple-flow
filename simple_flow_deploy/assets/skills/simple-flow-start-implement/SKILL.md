---
name: simple-flow-start-implement
description: Implement one clearly approved conversational proposal through a GitHub Issue and pull request to the repository's main merge route.
---

# Simple Flow Start-Implement

Use this skill when the user asks to implement a proposal that was discussed or
drafted in the current conversation.

On Windows, use PowerShell-compatible Git and GitHub CLI commands; do not
assume Bash-only utilities are available.

## Select the work

Infer the intended proposal from the current conversation. Proceed without
asking for an ID when exactly one approved, implementation-ready proposal is
clearly relevant.

Ask the user to choose only if the conversation contains multiple plausible
proposals, or the candidate is missing a decision needed to implement safely.
Present the short candidate titles rather than asking for a legacy Draft ID.

If the user supplied an Issue number or URL, use it. Otherwise search the
repository's open Issues for a clearly matching issue before creating one. If
none exists, create an Issue from the approved conversational proposal.

## Implement through GitHub

1. Discover the repository and its default branch from the local `origin` and
   GitHub CLI. Use the default branch as the PR base (normally `main`); do not
   ask for values that are available locally.
2. Create or reuse the matching GitHub Issue. Its body must preserve the
   agreed outcome, acceptance criteria, scope, and out-of-scope limits.
3. Create a branch bound to that Issue, for example
   `feature/<issue-number>-<short-slug>`.
4. For a FEATURE, add a failing test when the project supports testing, make
   the smallest implementation that satisfies the proposal, then run relevant
   tests. For DOCUMENTATION, change only the agreed documentation.
5. Commit and push the change. Open a pull request against the default branch
   with `Closes #<issue-number>` in its body, the acceptance evidence, and the
   changed-file scope. Create it ready for review once tests pass; otherwise
   leave it as a draft and report the blocker.
6. Report the Issue and PR URLs, test results, and any remaining review work.
   Do not merge.

## Boundaries

- Do not require or create hidden project state, a Draft ID, or a draft file.
- Do not rewrite the approved proposal while implementing it.
- Do not create duplicate Issues for the same approved work.
- Do not merge; only PR-Finalize may merge after the user explicitly accepts
  the pull request.
