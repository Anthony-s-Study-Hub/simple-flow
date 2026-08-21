# Simple Flow

Simple Flow is a controlled development workflow study. Phase 1 builds the
deterministic GitHub and CI governance layer before any agent skills are added.

The phase 1 implementation lives in `simple_flow_gates` and validates:

- fixed issue contracts for `FEATURE` and `DOCUMENTATION`
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

Phase 4 adds `phase4-run`, a real workflow experiment harness. It resets a
dedicated test project, deploys the current workflow package, launches isolated
agent turns with fixed scenario prompts, collects objective Git/GitHub evidence,
and writes compact JSON plus Markdown experiment reports. Codex CLI remains the
default backend, and an OpenAI-compatible local LLM backend can run the same
smoke scenarios without Codex token usage. Source CI validates the harness and
scenario catalog statically; it does not run live agent experiments
automatically.

Run the local test suite:

```powershell
python -m pytest
```

Run the gate CLI against a GitHub Actions event payload:

```powershell
python -m simple_flow_gates.cli validate-pr --event-path $env:GITHUB_EVENT_PATH
```

Validate Phase 4 static definitions:

```powershell
python -m simple_flow_test_harness.cli validate
```

Run the live Phase 4 smoke-gated experiment explicitly:

```powershell
python -m simple_flow_test_harness.cli run --allow-remote-reset
```

Probe and run the local OpenAI-compatible backend:

```powershell
python -m simple_flow_test_harness.cli probe-local-llm `
  --local-llm-url http://169.254.83.107:1234 `
  --local-llm-model google/gemma-4-e4b

python -m simple_flow_test_harness.cli run --smoke-only `
  --agent-backend local-openai `
  --local-llm-url http://169.254.83.107:1234 `
  --local-llm-model google/gemma-4-e4b `
  --allow-remote-reset
```

The default run uses the smoke set first, a 60 second per-turn timeout, and the
mini Codex model preference when the Codex backend is selected. The smoke set
includes a remote Issue/PR artifact scenario. The full scenario set runs only
after smoke passes. See
`docs/phase4-scenario-impact.md` for each scenario goal and remote mutation
impact.

Phase 5 adds the Documentation-Curation skill and deterministic
`simple_flow_documentation_curation` helpers. The skill turns normalized
Issue/PR/review history into Decision Proposals, Documentation Findings, New
Component Proposals, and a DOCUMENTATION Canonical Draft, then stops before the
existing documentation workflow begins. The portable installer includes the
sixth skill and baseline templates under `.simple-flow/baselines/`.
