# Skill Toolkit Deployment

Simple Flow is deployed as a reusable agent-skill toolkit. It installs only
agent skills and the `.simple_tool/` workflow runtime and state scaffold; it
does not install target CI workflows, root application packages, tests,
documentation, governance files, or root configuration.

From a target project root:

```powershell
uvx --from git+https://github.com/Anthony-s-Study-Hub/simple-flow.git@v0.2.2 simple-flow doctor .
uvx --from git+https://github.com/Anthony-s-Study-Hub/simple-flow.git@v0.2.2 simple-flow install .
```

The default install copies the six canonical skills to both supported
project-local protocols:

```text
.codex/skills/<short-skill-name>/SKILL.md
.claude/skills/<short-skill-name>/SKILL.md
.simple_tool/
```

Use `--agent codex` or `--agent claude` to install only one protocol. `plan`
is read-only, and repeated installs are idempotent. The installer reports a
conflict instead of overwriting a locally customized skill.

## Included skills

- `discussion`
- `issue-draft`
- `start-implement`
- `review-triage`
- `pr-finalize`
- `documentation-curation`

Skill-local scripts are copied beside their `SKILL.md` files, and their shared
runtime is copied under `.simple_tool/runtime/`, so they remain runnable after
deployment. Issue-Draft writes Canonical Drafts beneath `.simple_tool/drafts/`;
Start-Implement selects that durable handoff before creating or reusing a
GitHub Issue and opening a PR against the repository default branch.
PR-Finalize merges only after explicit user acceptance and objective GitHub
checks.

Issue-Draft retains the typed Issue contract in each draft's Markdown and adds
execution metadata only to the JSON draft. Start-Implement uses its bundled
`plan_implementation.py` helper to choose an eligible draft from explicit
references, durable state, or structured agent-produced intent evidence. The
planner fixes the implementation route and constraints before an agent writes
FEATURE code or non-mechanical DOCUMENTATION content.
