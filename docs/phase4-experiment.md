# Phase 4 Real Codex Workflow Experiment

Phase 4 adds an explicit experiment harness around the deployed Simple Flow
workflow. It is executable validation code, not an automatic source CI test.

## Entry Point

Run static validation:

```powershell
python -m simple_flow_phase4.cli validate
```

Run all live scenarios:

```powershell
python -m simple_flow_phase4.cli run `
  --test-repo-url https://github.com/Anthony-s-Study-Hub/simple-flow-test.git `
  --gh-path "C:\Program Files\GitHub CLI\gh.exe" `
  --allow-remote-reset
```

Run one scenario:

```powershell
python -m simple_flow_phase4.cli run --scenario A01 --allow-remote-reset
```

Generate a CI-safe report without launching Codex:

```powershell
python -m simple_flow_phase4.cli run --scenario A01 --dry-run
```

## Boundaries

- Source CI may run `validate` and dry-run schema checks.
- Source CI must not run the live Codex experiment.
- The harness resets the dedicated test repository before each scenario when
  `--allow-remote-reset` is supplied.
- The Agent Under Test runs through `codex exec --ephemeral` in the scenario
  test project.
- The harness may fill only mechanical variables such as Draft ID, Issue number,
  PR number, and branch name.
- Objective PASS / FAIL / BLOCKED / ERROR status is assigned by deterministic
  code after the Codex process exits.
- Post-run diagnosis is recorded separately and never rewrites objective status.

## Reports

Each run writes:

- `.simple-flow/phase4-reports/<run-id>.json`
- `.simple-flow/phase4-reports/<run-id>.md`
- `.simple-flow/phase4-reports/latest.json`
- `.simple-flow/phase4-reports/latest.md`

Reports include scenario IDs, prompt references, expected and observed state,
evidence, status, failure reason, test repository references, Codex CLI version,
workflow package version, harness commit SHA, and timestamp.
