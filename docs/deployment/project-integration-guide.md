# Project Integration Guide

Install the Simple Flow skills at the project root. The installer creates only
the chosen agent skill directories:

```text
.codex/skills/simple-flow-*/SKILL.md
.claude/skills/simple-flow-*/SKILL.md
```

No repository policy, application module, CI workflow, test, documentation
folder, or hidden workflow-state directory is installed. Project conventions,
existing CI, and GitHub configuration remain owned by the project.

Use Discussion and Issue-Draft to establish an implementation-ready proposal
in chat. When the user asks to implement it, Start-Implement infers the single
clear proposal, creates or reuses a GitHub Issue, and opens a PR against the
repository default branch. It asks the user to choose only when the discussion
contains multiple viable proposals. PR-Finalize requires explicit merge
approval from the user.
