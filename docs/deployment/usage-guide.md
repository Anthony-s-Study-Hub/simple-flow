# Simple Flow Usage Guide

The toolkit provides five project-local agent skills. Use the same skill names
from Codex or Claude after installation.

1. Use `simple-flow-issue-draft` to turn an agreed result into one
   implementation-ready Canonical Draft in `.simple_tool/drafts/`.
2. When the user asks to implement the proposal, use
   `simple-flow-start-implement`. It reads the selected file-backed draft,
   creates or reuses the matching GitHub Issue, opens its bound draft PR before
   implementation, and leaves it ready for review only after required CI passes.
3. Use `simple-flow-review-triage` for proposal changes or review findings that
   need an explicit successor route.
4. After the user explicitly approves a PR for merge, use
   `simple-flow-pr-finalize` to verify and merge it through the repository's
   normal default-branch route.
5. Use `simple-flow-documentation-curation` to derive a documentation-change
   proposal from project history.

The installer creates `.simple_tool/` for durable drafts, handoffs, triage,
evidence, temporary files, status, and its self-contained runtime. It does not
install target CI, root source packages, governance files, tests, or docs.
Start-Implement asks only when structured selection finds a material tie. It
stores delivery records beneath `.simple_tool/deliveries/`; other skills may not
modify those transition files.
