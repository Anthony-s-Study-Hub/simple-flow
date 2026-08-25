# Skill Toolkit Deployment

Simple Flow is deployed as a reusable agent-skill toolkit. It does not install
CI workflows, application code, tests, documentation, configuration files, or
project-local workflow state.

From a target project root:

```powershell
uvx --from git+https://github.com/Anthony-s-Study-Hub/simple-flow.git@v0.2.0 simple-flow doctor .
uvx --from git+https://github.com/Anthony-s-Study-Hub/simple-flow.git@v0.2.0 simple-flow install .
```

The default install copies the six canonical skills to both supported
project-local protocols:

```text
.codex/skills/simple-flow-*/SKILL.md
.claude/skills/simple-flow-*/SKILL.md
```

Use `--agent codex` or `--agent claude` to install only one protocol. `plan`
is read-only, and repeated installs are idempotent. The installer reports a
conflict instead of overwriting a locally customized skill.

## Included skills

- `simple-flow-discussion`
- `simple-flow-issue-draft`
- `simple-flow-start-implement`
- `simple-flow-review-triage`
- `simple-flow-pr-finalize`
- `simple-flow-documentation-curation`

The skills carry their workflow in conversation context. In particular,
Start-Implement infers one clearly approved proposal from the conversation,
creates or reuses a GitHub Issue, and opens a PR against the repository's
default branch. It asks for a choice only when the intended proposal is
ambiguous. PR-Finalize merges only after explicit user acceptance and objective
GitHub checks.
