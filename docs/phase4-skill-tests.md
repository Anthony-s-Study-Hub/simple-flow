# Phase 4 Skill-Test Feasibility Pilot

## Purpose and boundary

This replaces the native/local-emulation design. Phase 4 evaluates the real
Codex or Claude developer harness through its SDK, routed to a local LLM. It
does not recreate skill discovery, inject `SKILL.md` content, or tell the agent
which helper, path, command, or tool to use. The legacy 38-scenario runner is
retained only as migration reference; it is not the design authority for this
pilot.

The pilot is intentionally small and uses a disposable, already-deployed test
project. Setup and fixtures are harness-side data, never agent prompt text.
P03 is a Start-Implement capability family: its approved-draft subcase creates
and proves real remote artifacts in the configured disposable repository.

## Execution and test nodes

`prepare fixture -> capture remote baseline (when required) -> unchanged developer prompt + SDK skill input -> pushed host events -> structured turn record -> local/remote snapshots -> fixed-manifest checks -> cleanup -> repeated-trial statistics`

| Node | Class | What it checks | Implementation |
| --- | --- | --- | --- |
| Local route | Infrastructure | The selected SDK is configured for the requested local endpoint/model. | Preflight checks the installed SDK and local `/v1/models`; adapter records host, endpoint, model, and provider. A routing/SDK failure is `BLOCKED`. |
| Prompt fidelity | Deterministic | The user request is a normal developer request, not a harness script. | Compares the submitted prompt byte-for-byte and rejects skill files, helper paths, commands, argv, or injected context. |
| Structured result | Deterministic | The test harness receives a complete machine-readable turn record. | Adapter normalizes session ID, terminal status, final text, and event count from SDK events. Optional agent JSON is retained as evidence, but cannot make a result pass. |
| Host trace | Deterministic | There is trace evidence to evaluate. | The adapters normalize pushed SDK events. There is no synthetic native-skill-discovery node. |
| Skill invocation | Deterministic | The requested skill reached the host harness. | Codex attaches the installed `SKILL.md` with SDK `SkillInput`, alongside the unchanged text prompt. |
| Precondition | Deterministic | Framework-owned mock inputs satisfy the scenario contract. | P03-R parses its independently seeded `DRAFT-0001` and requires `DOCUMENTATION_NORMAL` before the SDK turn can start. |
| Objective state | Deterministic | The resulting local project state meets the scenario oracle. | Before/after snapshots count drafts, changed paths, and implementation branches. |
| Remote state | Deterministic | A remote-capable scenario made exactly the declared GitHub change. | The verifier captures baseline/final GitHub state and compares it with a fixed manifest: Issue/branch/PR fields, branch ancestry, exact files, merge state, and optional CI policy. |
| Remote cleanup | Deterministic | Remote test state is removed after evidence capture. | The verifier closes each run-created PR, deletes its branch, closes each run-created Issue with the fixed cleanup note, and then verifies the resulting remote state. |
| Workflow outcome | Agent capability | The agent produces the required skill outcome. | Combines terminal SDK completion with the independent state oracle. |
| Stop boundary | Agent capability | The agent ended at the intended workflow boundary. | Requires terminal completion and the state oracle showing no prohibited continuation, including P03's unmerged draft PR. |

The agent's structured result is evidence, not the verdict. The harness derives
all objective-state verdicts from observations and cross-checks capability
claims against the host trace.

## Pilot scenarios

| ID | Testing goal | Input prompt | Passing criteria |
| --- | --- | --- | --- |
| P01 | Discussion stays exploratory. | `@discussion "Explore adding a lightweight health endpoint. Give concise options, risks, and open questions; then stop."` | SDK-attached discussion skill; complete turn record; no new draft, workspace change, or implementation branch. |
| P02 | Issue-Draft makes formal work but stops before implementation. | `@issue-draft FEATURE: Add a lightweight health endpoint with a JSON status response. Requirements: provide GET /health and return a JSON status value. Acceptance criteria: a healthy service returns HTTP 200 with JSON status; the endpoint is documented. Scope: the health endpoint and its focused tests. Out of scope: dependency health checks and unrelated refactoring. Documentation impact: update the usage guide. Roadmap target: UNMAPPED.` | SDK-attached issue-draft skill; complete turn record; at least one new draft and no implementation branch. |
| P03-U | Start-Implement handles an unmet prerequisite. | `@start-implement DRAFT-9999` | SDK-attached start-implement skill; complete turn record; no local or remote work artifact. |
| P03-R | Start-Implement executes an approved, independent DOCUMENTATION draft. | `@start-implement DRAFT-0001` | One exact-title Issue; branch `documentation/<new issue number>-phase4-smoke` descended from captured `main`; one open draft PR with exact title/base/head; exact expected documentation content; no merge or extra remote artifact. |

Prompts are passed verbatim as SDK text input. The skill reference, output
schema, project location, and observation plan are transport configuration, so
they do not change the developer request being evaluated.

P02 also creates a validated, approved draft-input fixture during harness setup
and attaches it as an SDK mention. The prompt neither names that file nor tells
the agent which command to run; Issue-Draft still owns validation, draft
creation, and its stop point.

P03-R independently seeds a canonical `DRAFT-0001` JSON/Markdown pair. The
fixed verifier, rather than agent prose, resolves the newly allocated Issue
number and uses it as the deterministic branch reference. Every reference is
recorded in the result: baseline SHA, Issue/PR number, expected branch, final
remote snapshot, and cleanup result. A separate SDK mention provides the
run-scoped repository and `gh` command; it is setup data, not prompt text.

## Remote-capability pipeline

Remote verification is part of the skill outcome, not a separate capability
test. A scenario opts in through a manifest with exact Issue title, branch
template, PR fields, expected file contents, merge state, and an optional CI
policy (`ignore`, `present`, or `success`). The same verifier can therefore
cover Issue opening, PR merge/finalization, and CI-dependent skills without
changing agent prompts.

Only `--remote-verify --allow-remote-reset` enables a remote scenario. Every
remote repetition uses the configured shared test repository
`Anthony-s-Study-Hub/simple-flow-test`, captures baseline/final evidence, then
closes the run-created PR and Issue (with `Closed by Simple Flow Phase 4 SDK
cleanup.`) and deletes its branch. The inner verifier cleans observed run
artifacts even when the agent or verification code fails mid-run, then verifies
the post-cleanup state.

## SDK routing and monitoring

- `openai-codex` drives Codex app-server with a named local provider and local
  base URL. `claude-code-sdk` drives Claude Code with `ANTHROPIC_BASE_URL` set
  to the local gateway. Both are installed through the `phase4-sdk` optional
  dependency group.
- The Claude route requires an Anthropic-message-compatible local gateway; an
  OpenAI-only `/v1` endpoint is not sufficient. The Codex route requires a
  Responses-compatible endpoint. Each incompatibility is an infrastructure
  `BLOCKED` result, never an agent failure.
- A run first uses `sdk-preflight`; a failed local route is `BLOCKED`, never a
  failed agent capability result.
- SDK event streams are consumed directly. After 60 seconds with no pushed
  event, the runner records one local liveness check and waits again. It never
  sends an agent “status” prompt or polls the model. The action timeout is a
  separate hard limit and must exceed that interval.

## Determinism and confidence

Infrastructure failures, prompt/result/trace validation, and state-oracle
checks are deterministic. They receive no confidence score.

Only `workflow_outcome` and `stop_boundary` are agent-capability checkpoints.
For each checkpoint and one fixed host/model/prompt/skill configuration, the
report contains valid trials `n`, passes `k`, pass rate `k/n`, and a 95% Wilson
interval. `BLOCKED` and `UNKNOWN` trials are shown separately and excluded from
the statistic. The CLI emits one confidence block per scenario; results are
never pooled across hosts, models, prompt versions, or skill versions.

## Commands

Use the project virtual environment so the SDK dependencies do not affect other
tools.

```powershell
.\.venv\Scripts\python.exe -m simple_flow_test_harness.cli sdk-preflight --sdk-host codex-sdk
.\.venv\Scripts\python.exe -m simple_flow_test_harness.cli sdk-pilot --sdk-host codex-sdk --dry-run
.\.venv\Scripts\python.exe -m simple_flow_test_harness.cli sdk-pilot --sdk-host codex-sdk --project-root <disposable-deployed-project> --repetitions 10 --action-timeout-seconds 900
.\.venv\Scripts\python.exe -m simple_flow_test_harness.cli sdk-pilot --sdk-host codex-sdk --scenario P03-R --remote-verify --allow-remote-reset --repetitions 5 --action-timeout-seconds 900
```

Use `--sdk-host claude-sdk` to exercise the Claude SDK route. A live run is
allowed only against the caller-supplied disposable project. For a
remote-capable scenario, the configured test-repository owner must permit
cleanup of Issues, PRs, and branches and the explicit remote-reset flag is
required.
