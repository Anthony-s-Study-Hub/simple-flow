---
name: simple-flow-pr-finalize
description: Explicitly merge and finalize the current Simple Flow delivery pull request.
---

# Simple Flow PR-Finalize

Use this skill only when the user explicitly invokes `$simple-flow-pr-finalize`.
It must not be invoked implicitly from ordinary conversation, including a
message that says a PR has passed review. The explicit invocation is the merge
authorization for the current delivery; do not ask for a second approval.
For this skill, explicit invocation is sufficient authorization.

On Windows, use PowerShell-compatible Git and GitHub CLI commands; do not
assume Bash-only utilities are available.

## Finalize the current delivery

Run this skill's bundled `scripts/finalize_remote_pr.py` with the repository
and its internal `--approved` flag. Pass `--pr` only when the user supplied a
specific PR as part of this explicit invocation. Otherwise, the script resolves
the current delivery deterministically: explicit PR, then
`.simple_tool/status.json` `active_pull_request`, then the unique delivery
record matching `active_issue`. If those sources do not identify exactly one
PR, report the script's structured blocker; do not guess from chat history.

The script may read existing Draft, Triage, Delivery, and status handoff files
as evidence. It must not modify their owned Draft, Triage, or Delivery records.
It verifies live GitHub state (default branch, open non-Draft state, required
checks, and unresolved review threads), merges remotely, and verifies `MERGED`.
After a verified merge it closes associated delivery or `Closes` Issues,
deletes only a same-repository non-default head branch, writes its own
`.simple_tool/finalizations/` record, and clears only active Issue/PR pointers
that still identify that finalized delivery.

## Boundaries

- Do not force merge, bypass protection, resolve reviews automatically, or fix
  failing checks.
- Do not merge an ambiguous PR or continue after any script-reported blocker.
