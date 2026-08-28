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

Use Issue-Draft to establish an implementation-ready proposal. When the user
asks to implement it, Start-Implement deterministically selects the Draft,
creates or reuses its GitHub Issue, and opens a draft PR against the repository
default branch before implementation. It stops with a review-ready PR only
after required CI passes. PR-Finalize requires explicit merge approval from the
user and performs the remote merge.
