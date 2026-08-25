# Simple Flow Usage Guide

The toolkit provides six project-local agent skills. Use the same skill names
from Codex or Claude after installation.

1. Use `simple-flow-discussion` to explore a request.
2. Use `simple-flow-issue-draft` to turn the agreed result into one
   implementation-ready Canonical Draft in `.simple_tool/drafts/`.
3. When the user asks to implement the proposal, use
   `simple-flow-start-implement`. It reads the selected file-backed draft,
   creates or reuses the matching GitHub Issue, makes the change on an
   Issue-bound branch, and opens a PR against the repository default branch.
4. Use `simple-flow-review-triage` for review findings that need classification.
5. After the user explicitly approves a PR for merge, use
   `simple-flow-pr-finalize` to verify and merge it through the repository's
   normal default-branch route.
6. Use `simple-flow-documentation-curation` to derive a documentation-change
   proposal from project history.

The installer creates `.simple_tool/` for durable drafts, handoffs, triage,
evidence, temporary files, status, and its self-contained runtime. It does not
install target CI, root source packages, governance files, tests, or docs.
Start-Implement asks the user to select a draft only when status and explicit
context do not identify exactly one approved draft.
