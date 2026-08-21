# Phase 4 Real Codex Workflow Experiment

Phase 4 adds an explicit experiment harness around the deployed Simple Flow
workflow. It is executable validation code, not an automatic source CI test.

## Entry Point

Run static validation:

```powershell
python -m simple_flow_phase4.cli validate
```

Run the default smoke-gated live experiment:

```powershell
python -m simple_flow_phase4.cli run `
  --test-repo-url https://github.com/Anthony-s-Study-Hub/simple-flow-test.git `
  --gh-path "C:\Program Files\GitHub CLI\gh.exe" `
  --allow-remote-reset
```

The default live run executes the smoke set first: A01, A02, A06, C01, and S01.
S01 is a smoke-only remote-artifact scenario that should create a GitHub Issue
and draft PR in the dedicated test repo from a harness-seeded approved
DOCUMENTATION draft. The full 25-scenario suite runs only when every smoke
scenario passes. This saves time and tokens when basic skill invocation,
workflow boundaries, or remote artifact creation are already broken.

Run only the smoke set:

```powershell
python -m simple_flow_phase4.cli run --smoke-only --allow-remote-reset
```

Run the full suite without the smoke gate for debugging:

```powershell
python -m simple_flow_phase4.cli run --no-smoke-gate --allow-remote-reset
```

Run one scenario:

```powershell
python -m simple_flow_phase4.cli run --scenario A01 --allow-remote-reset
```

Selected scenarios run directly and do not trigger the default smoke gate.

Generate a CI-safe report without launching Codex:

```powershell
python -m simple_flow_phase4.cli run --scenario A01 --dry-run
```

Live runs default to a 60 second per-turn timeout and `gpt-5.4-mini` to keep the
experiment small. Override these when the local Codex installation does not have
that model or a scenario needs more room:

```powershell
python -m simple_flow_phase4.cli run `
  --codex-model gpt-5.4 `
  --timeout-seconds 180 `
  --allow-remote-reset
```

## Boundaries

- Source CI may run `validate` and dry-run schema checks.
- Source CI must not run the live Codex experiment.
- Local `pytest` and `--dry-run` commands do not mutate the remote test repo.
- The harness resets the dedicated test repository before each scenario when
  `--allow-remote-reset` is supplied.
- Live harness setup can mutate the remote test repo before any scenario action
  by force-pushing the baseline, closing open test issues and PRs, and deleting
  non-baseline branches.
- The Agent Under Test runs through isolated `codex exec` sessions in the
  scenario test project.
- The harness may fill only mechanical variables such as Draft ID, Issue number,
  PR number, and branch name.
- Scenarios may declare explicit local fixtures, such as S01's approved
  Canonical Draft, when setup data is needed to keep the live action small and
  deterministic.
- Objective PASS / FAIL / BLOCKED / ERROR status is assigned by deterministic
  code after the Codex process exits.
- Post-run diagnosis is recorded separately and never rewrites objective status.

## Reports

Each run writes:

- `.simple-flow/phase4-reports/<run-id>.json`
- `.simple-flow/phase4-reports/<run-id>.md`
- `.simple-flow/phase4-reports/latest.json`
- `.simple-flow/phase4-reports/latest.md`

Reports include scenario IDs, smoke-gate metadata, prompt references, expected
and observed state, compact evidence, status, failure reason, test repository
references, Codex CLI version, workflow package version, harness commit SHA, and
timestamp.

The Markdown report is intentionally compact. For each USER_ACTION, fixed
harness code records the processed fixture prompt fields, especially the action
sent to Codex, and the processed response received from Codex. Raw JSON event
streams and long command output are summarized deterministically in
`simple_flow_phase4.transcript` before they enter the human-readable report.

## Scenario Impact

The per-scenario goal and mutation matrix lives in
[`docs/phase4-scenario-impact.md`](phase4-scenario-impact.md). It documents
which commands are local-only, which live runs can mutate the remote test repo,
and whether each scenario expects the Agent Under Test to create or merge remote
GitHub artifacts.
