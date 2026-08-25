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

Phase 3 adds a deterministic release installer for deploying the portable skill
toolkit into another project. From a new project root:

```powershell
uvx --from git+https://github.com/Anthony-s-Study-Hub/simple-flow.git@v0.2.0 simple-flow doctor .
uvx --from git+https://github.com/Anthony-s-Study-Hub/simple-flow.git@v0.2.0 simple-flow install .
```

The default release install copies only the six skill `SKILL.md` files to both
`.codex/skills/` and `.claude/skills/`; it does not add workflow state, CI,
documentation, or source code to the project. Use `--agent codex` or
`--agent claude` for a single protocol.

Phase 4 adds `phase4-run`, a real workflow experiment harness. It resets a
dedicated test project, deploys the current workflow package, launches isolated
agent turns with fixed scenario prompts, collects objective Git/GitHub evidence,
and writes compact JSON plus Markdown experiment reports. Reports include
deterministic skill invocation checkpoints so helper-script mechanics can be
distinguished from broader agent autonomy. Codex CLI remains the default
backend; it can run either the normal Codex model route or a local OSS provider
such as LM Studio. An OpenAI-compatible local LLM backend is also available for
direct tool-loop experiments. Source CI validates the harness and scenario
catalog statically; it does not run live agent experiments automatically.

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

Probe and run Codex itself against a local LM Studio model:

```powershell
python -m simple_flow_test_harness.cli probe-codex-local-llm `
  --local-llm-url http://169.254.83.107:1234 `
  --local-llm-model google/gemma-4-e4b `
  --codex-local-provider lmstudio

python -m simple_flow_test_harness.cli run --smoke-only `
  --agent-backend codex `
  --codex-oss `
  --codex-local-provider lmstudio `
  --codex-model google/gemma-4-e4b `
  --allow-remote-reset
```

The default run uses the smoke set first, a 60 second per-turn timeout, and the
mini Codex model preference when the Codex backend is selected. The smoke set
includes Issue-Draft, Review-Triage, Documentation-Curation, policy-boundary,
and remote Issue/PR artifact coverage. The full scenario set runs only after
smoke passes. See
`docs/phase4-scenario-impact.md` for each scenario goal and remote mutation
impact.

Phase 5 adds the Documentation-Curation skill. The skill turns project history
into a reviewable DOCUMENTATION Canonical Draft under `.simple_tool/`, which is
the installed workflow state owned by the portable toolkit.
