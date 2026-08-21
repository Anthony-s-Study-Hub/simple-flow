# Phase 3 Deployment

Phase 3 packages the controlled development workflow so it can be installed into
another project without changing core workflow logic.

## Installer

Run:

```powershell
python scripts/install_simple_flow.py --target C:\path\to\target-project
```

The installer reports created, skipped, conflicts, and failures as JSON.

Installed target skills are placed under `.codex/skills` with unprefixed names:

- `discussion`
- `issue-draft`
- `start-implement`
- `review-triage`
- `pr-finalize`

## Installed Files

The installer deploys:

- `AGENTS.md`
- GitHub workflows and templates
- Phase 1 validators and automation
- Phase 2 deterministic helpers
- five Codex skills with target-safe names
- project configuration template
- usage, integration, and GitHub setup docs

## Known Limits

The installer performs deterministic file deployment and static validation. It
does not create GitHub Projects fields, choose project roadmap targets, or
replace human semantic review.

