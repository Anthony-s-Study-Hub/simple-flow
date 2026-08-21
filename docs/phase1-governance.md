# Phase 1 Governance

Phase 1 is deliberately deterministic. The issue and PR templates define the
human-facing contract; the Python validators are the single implementation used
by both CI and tests.

## Contracts

`FEATURE` issues must use the exact field order in the feature template.
`DOCUMENTATION` issues must use the exact field order in the documentation
template. Unknown top-level fields fail validation.

Pull requests must keep the fixed PR template fields and link exactly one issue.
Development branches must include the same issue number, for example:

```text
feature/123-short-name
documentation/124-usage-guide
issue/125-ci-fix
sf-126-small-change
```

## TDD Evidence

`FEATURE` work must add evidence at:

```text
.simple-flow/tdd-evidence/<issue-number>.json
```

The evidence format is:

```json
{
  "issue": 123,
  "red": {
    "commit": "<red-test-commit-sha>",
    "command": "python -m pytest tests/test_example.py",
    "exit_code": 1
  },
  "implementation": {
    "commit": "<implementation-commit-sha>"
  },
  "green": {
    "commit": "<green-commit-sha>",
    "command": "python -m pytest",
    "exit_code": 0
  }
}
```

The TDD governance checks verify that RED failed, GREEN passed, and the commits
appear in the pull request history in RED, implementation, GREEN order. CI
reports this as separate TDD evidence, RED replay, and GREEN replay checks so
the failing and passing phases remain visible without weakening the merge gate.

## Scope And Docs

`FEATURE` scope is read from the issue `Scope` field. `DOCUMENTATION` scope is
read from `Affected Project Documents`.

`DOCUMENTATION` work is documentation-only. Its affected paths must be normal
documentation locations such as `docs/`, root documentation files like
`README.md` or `AGENTS.md`, or Markdown issue templates under
`.github/ISSUE_TEMPLATE/`. Functioning-code paths such as `simple_flow_gates/`,
`simple_flow_agent/`, `scripts/`, `skills/`, and `tests/` fail validation even
if they are listed in `Affected Project Documents`.

`Documentation Impact = None` means no documentation file is required. Any other
value is treated as a list of required documentation paths or glob patterns.

## Merge Settings

The desired repository settings are:

```json
{
  "delete_branch_on_merge": true,
  "allow_auto_merge": false
}
```

The desired main branch policy includes admins in enforcement and requires pull
requests, resolved review conversations, no force pushes, no branch deletion,
and zero required approving reviews while the agent and human share one GitHub
identity.

Required PR checks are intentionally granular:

- `pr-contract`
- `linked-issue-contract`
- `scope-governance`
- `documentation-impact`
- `tdd-evidence-order`
- `tdd-red-replay`
- `tdd-green-replay`
- `current-head-tests`

Issue contract validation runs from the issue-only `issue-contract` check and
is revalidated on PRs through `linked-issue-contract`.

Apply the policy from a local workstation with the full GitHub CLI path:

```powershell
.\scripts\configure_repository.ps1 -GhPath "C:\Program Files\GitHub CLI\gh.exe"
```
