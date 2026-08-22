# Phase 4 Real Agent Workflow Experiment

Phase 4 adds an explicit experiment harness around the deployed Simple Flow
workflow. It is executable validation code, not an automatic source CI test.

## Entry Point

Run static validation:

```powershell
python -m simple_flow_test_harness.cli validate
```

Run the default smoke-gated live experiment:

```powershell
python -m simple_flow_test_harness.cli run `
  --test-repo-url https://github.com/Anthony-s-Study-Hub/simple-flow-test.git `
  --gh-path "C:\Program Files\GitHub CLI\gh.exe" `
  --allow-remote-reset
```

The default live run executes the smoke set first: A01, A02, A06, C01, E01, and
S01. A02 uses a deterministic local JSON input fixture for `@issue-draft`; E01
uses deterministic history and analysis fixtures for `@documentation-curation`;
S01 is a smoke-only remote-artifact scenario that should create a GitHub Issue
and draft PR in the dedicated test repo from a harness-seeded approved
DOCUMENTATION draft. The full 37-scenario suite runs only when every smoke
scenario passes.
Smoke scenarios that are also part of the full suite are not repeated after the
gate passes; the second phase runs only the remaining full-suite scenarios.
This saves time and tokens when basic skill invocation, workflow boundaries, or
remote artifact creation are already broken.

Run only the smoke set:

```powershell
python -m simple_flow_test_harness.cli run --smoke-only --allow-remote-reset
```

Run the full suite without the smoke gate for debugging:

```powershell
python -m simple_flow_test_harness.cli run --no-smoke-gate --allow-remote-reset
```

Run one scenario:

```powershell
python -m simple_flow_test_harness.cli run --scenario A01 --allow-remote-reset
```

Selected scenarios run directly and do not trigger the default smoke gate.

Generate a CI-safe report without launching the selected backend:

```powershell
python -m simple_flow_test_harness.cli run --scenario A01 --dry-run
```

Live runs default to the `codex` backend, a 60 second per-turn timeout, and
`gpt-5.4-mini` to keep the experiment small. Override these when the local Codex
installation does not have that model or a scenario needs more room:

```powershell
python -m simple_flow_test_harness.cli run `
  --codex-model gpt-5.4 `
  --timeout-seconds 180 `
  --allow-remote-reset
```

The harness can also use an OpenAI-compatible local LLM backend. This route uses
`/v1/models`, `/v1/chat/completions`, and function/tool calls; it does not invoke
`codex exec`.

Probe the local backend:

```powershell
python -m simple_flow_test_harness.cli probe-local-llm `
  --local-llm-url http://169.254.83.107:1234 `
  --local-llm-model google/gemma-4-e4b
```

Run the smoke set through the local backend:

```powershell
python -m simple_flow_test_harness.cli run --smoke-only `
  --agent-backend local-openai `
  --local-llm-url http://169.254.83.107:1234 `
  --local-llm-model google/gemma-4-e4b `
  --allow-remote-reset
```

The local backend exposes controlled tools such as `run_command`, `read_file`,
and `list_files` to the model. Scenario prompts still use the same generic
USER_ACTION skill aliases; backend-specific execution is invisible to scenario
definitions.

Live runs also default to Codex sandbox bypass because remote-mutation scenarios
must create Git branches, commits, pushes, Issues, and draft PRs inside the
dedicated throwaway test workspace. Use `--codex-full-auto-sandbox` only when
diagnosing sandbox behavior; S01 is expected to block in that mode because Git
branch creation cannot complete.

## Boundaries

- Source CI may run `validate` and dry-run schema checks.
- Source CI must not run the live agent experiment.
- Local `pytest` and `--dry-run` commands do not mutate the remote test repo.
- `probe-local-llm` checks the local endpoint only; it does not mutate the remote
  test repo.
- The harness resets the dedicated test repository before each scenario when
  `--allow-remote-reset` is supplied.
- Live harness setup can mutate the remote test repo before any scenario action
  by force-pushing the baseline, closing open test issues and PRs, and deleting
  non-baseline branches.
- The Agent Under Test runs through the selected backend in the scenario test
  project. `codex` uses isolated `codex exec` sessions; `local-openai` uses an
  OpenAI-compatible local endpoint plus controlled tools.
- The harness may fill only mechanical variables such as Draft ID, Issue number,
  PR number, and branch name.
- Scenarios may declare explicit local fixtures, such as A02's draft input file
  and S01's approved Canonical Draft, when setup data is needed to keep the live
  action small and deterministic.
- Objective PASS / FAIL / BLOCKED / ERROR status is assigned by deterministic
  code after the agent turn exits.
- Post-run diagnosis is recorded separately and never rewrites objective status.

## Reports

Each run writes:

- `.simple-flow/phase4-reports/<run-id>.json`
- `.simple-flow/phase4-reports/<run-id>.md`
- `.simple-flow/phase4-reports/latest.json`
- `.simple-flow/phase4-reports/latest.md`

Reports include scenario IDs, smoke-gate metadata, prompt references, expected
and observed state, compact evidence, status, failure reason, test repository
references, selected backend, selected model, endpoint, whether Codex CLI was
used, Codex CLI version when applicable, workflow package version, harness commit
SHA, skill invocation checkpoints, confidence band, and timestamp.

Skill invocation checkpoints are deterministic report fields derived from the
observed tool trace and final repository state. They separate harness and skill
mechanism confidence from broader agent autonomy:

- Skill discovery: whether the selected backend exposed the intended skill.
- Instruction exposure: whether the relevant `SKILL.md` context was loaded when
  observable.
- Helper intent: whether the agent attempted the expected skill-owned helper
  script.
- Command shape: whether that helper was invoked as an executable command rather
  than shell-only syntax.
- Helper execution: whether the helper exited successfully.
- Side effect: whether deterministic objective rules observed the expected local
  or remote mutation.
- Stop point: whether output included a recognizable stop or finish marker.

Confidence bands are HIGH, MEDIUM, LOW, HARNESS_ISSUE, or UNKNOWN. A LOW result
usually means the selected model did not translate skill instructions into the
expected helper call. A HARNESS_ISSUE result means the harness failed before that
agent capability question could be evaluated.

The Markdown report is intentionally compact. For each USER_ACTION, fixed
harness code records the processed fixture prompt fields, especially the action
sent to the selected backend, and the processed response received from that
backend. Raw JSON event streams and long command output are summarized
deterministically in
`simple_flow_test_harness.transcript` before they enter the human-readable report.

## Scenario Impact

The per-scenario goal and mutation matrix lives in
[`docs/phase4-scenario-impact.md`](phase4-scenario-impact.md). It documents
which commands are local-only, which live runs can mutate the remote test repo,
and whether each scenario expects the Agent Under Test to create or merge remote
GitHub artifacts.
