# Phase 4 SDK Skill-Test Suite

## Purpose

Phase 4 evaluates the real Codex or Claude SDK harness, routed to a local LLM.
It does not emulate a native harness or place helper commands in the developer
prompt. The harness attaches the installed skill and any framework-owned input,
then derives verdicts from SDK events and observed local or GitHub state.

## Test nodes

| Node | Type | Purpose and implementation |
| --- | --- | --- |
| Local route | Infrastructure | Confirms the selected SDK and local endpoint are reachable. A route failure is `BLOCKED`. |
| Prompt fidelity | Deterministic | Compares the exact submitted developer request to the scenario prompt and rejects harness mechanics in it. |
| Structured result / host trace | Deterministic | Normalizes SDK session, completion, final text, and pushed events into one machine-readable turn record. |
| Skill delivery | Deterministic | Attaches the installed `SKILL.md` with SDK skill input. |
| Helper execution | Deterministic | Extracts completed command events, redacts credentials, and matches each required skill script plus its fixed exit code. Source reads do not count as execution. |
| Response contract | Deterministic | Checks only scenario-required response facts from the captured final text. |
| Precondition / objective | Deterministic | Seeds and validates mock inputs, then checks local drafts, changed paths, branches, or a fixed remote manifest. |
| Remote cleanup | Deterministic | Closes run-owned PRs, deletes remaining branches, closes Issues with `Closed by Simple Flow Phase 4 SDK cleanup.`, and verifies the resulting state. |
| Workflow outcome / stop boundary | Agent capability | Combines completed turn, required helper evidence, response facts, and objective state. Only these two nodes receive repeated-trial statistics. |

The runner waits for 60 seconds of SDK-event silence before one local liveness
record; it never polls or sends a follow-up agent request.

## Scenarios

| ID | Skill and goal | Developer prompt | Passing criteria |
| --- | --- | --- | --- |
| P02 | Issue-Draft: create a FEATURE draft and stop. | `@issue-draft FEATURE: Add a lightweight health endpoint with a JSON status response. Requirements: provide GET /health and return a JSON status value. Acceptance criteria: a healthy service returns HTTP 200 with JSON status; the endpoint is documented. Scope: the health endpoint and its focused tests. Out of scope: dependency health checks and unrelated refactoring. Documentation impact: update the usage guide. Roadmap target: UNMAPPED.` | `create_draft.py` exits 0; at least one draft; no implementation branch. |
| P03-U | Start-Implement: reject an absent prerequisite. | `@start-implement DRAFT-9999` | `plan_implementation.py` returns its expected missing-draft exit; no local or remote artifact. |
| P03-R | Start-Implement: open the approved DOCUMENTATION delivery PR. | `@start-implement DRAFT-0001` | Framework seeds a valid independent draft; `plan_implementation.py` and `delivery_pr.py` open the exact Issue, branch, and draft PR; no merge. |
| P04 | Review-Triage: classify a blocking current-work finding. | `@review-triage relationship=CURRENT merge-impact=BLOCKING source-issue=42 source-pr=84 reason='The new endpoint omits an error response test.'` | `classify_finding.py` exits 0; response contains `CURRENT`, `BLOCKING`, `42`, and `84`; no workflow mutation. |
| P05 | Documentation-Curation: curate supplied history into one draft. | `@documentation-curation Curate the provided history into baseline update proposals and one DOCUMENTATION Canonical Draft; then stop.` | `curate_documentation.py` exits 0; one or more drafts and curation outputs only; no branch or remote artifact. |
| P06 | PR-Finalize: complete an accepted ready PR. | `@pr-finalize <fixture-pr-number>` | Framework seeds an open, non-draft PR with fixed objective state; `finalize_remote_pr.py` exits 0; PR is merged, linked Issue closed, head branch deleted, and exact file content reaches `main`. |

`<fixture-pr-number>` is the only run-scoped prompt substitution: it is the
normal user-visible subject required by PR-Finalize, not a harness instruction.
All other setup values are SDK attachments rather than prompt text.

## Remote pipeline

All remote tests use `Anthony-s-Study-Hub/simple-flow-test`. Each scenario gets
a fresh local clone that is removed afterward. P03-R creates its own artifacts.
P06 creates its fixture before the SDK turn, then verifies the specific seeded
Issue, PR, branch, and final `main` content. The shared repository is never
deleted or recreated by cleanup.

Remote tests require both `--remote-verify` and `--allow-remote-reset`.

## Confidence

Deterministic and infrastructure nodes have no confidence score. For each
scenario, model, host, skill version, and exact prompt configuration, repeated
trials produce `n`, `k`, pass rate, and a 95% Wilson interval for
`workflow_outcome` and `stop_boundary`. `BLOCKED` and `UNKNOWN` trials are
reported separately and excluded from the interval.

## Commands

```powershell
.\.venv\Scripts\python.exe -m simple_flow_test_harness.cli sdk-preflight --sdk-host codex-sdk
.\.venv\Scripts\python.exe -m simple_flow_test_harness.cli sdk-pilot --sdk-host codex-sdk --dry-run
.\.venv\Scripts\python.exe -m simple_flow_test_harness.cli sdk-pilot --sdk-host codex-sdk --remote-verify --allow-remote-reset --repetitions 3 --action-timeout-seconds 900
```
