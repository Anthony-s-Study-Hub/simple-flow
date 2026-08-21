# Simple Flow

Simple Flow is a controlled development workflow study. Phase 1 builds the
deterministic GitHub and CI governance layer before any agent skills are added.

The phase 1 implementation lives in `simple_flow_gates` and validates:

- fixed issue contracts for `FEATURE` and `PROJECT_CHANGE`
- PR body structure and issue traceability
- branch-to-issue binding
- TDD RED to implementation to GREEN evidence for `FEATURE`
- deterministic file scope and documentation impact rules
- orphan development branches without open pull requests

Phase 2 adds `AGENTS.md`, five Codex skill entrypoints under `skills/`, bundled
skill-local scripts for executable stage handoffs, and deterministic helpers in
`simple_flow_agent` for draft handoff, review triage, start-implement path
selection, and PR-finalize prechecks.

Phase 3 adds a deterministic installer in `scripts/install_simple_flow.py` for
deploying the portable workflow into another project.

Run the local test suite:

```powershell
python -m pytest
```

Run the gate CLI against a GitHub Actions event payload:

```powershell
python -m simple_flow_gates.cli validate-pr --event-path $env:GITHUB_EVENT_PATH
```
