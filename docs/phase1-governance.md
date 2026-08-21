# Phase 1 Governance

Phase 1 is deliberately deterministic. The issue and PR templates define the
human-facing contract; the Python validators are the single implementation used
by both CI and tests.

## Contracts

`FEATURE` issues must use the exact field order in the feature template.
`PROJECT_CHANGE` issues must use the exact field order in the project-change
template. Unknown top-level fields fail validation.

Pull requests must keep the fixed PR template fields and link exactly one issue.
Development branches must include the same issue number, for example:

```text
feature/123-short-name
project-change/124-baseline-update
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

The gate verifies that RED failed, GREEN passed, and the commits appear in the
pull request history in RED, implementation, GREEN order.

## Scope And Docs

`FEATURE` scope is read from the issue `Scope` field. `PROJECT_CHANGE` scope is
read from `Affected Project Documents`.

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

The desired main branch policy requires pull requests, required status checks,
resolved review conversations, no force pushes, no branch deletion, and zero
required approving reviews while the agent and human share one GitHub identity.

Apply the policy from a local workstation with the full GitHub CLI path:

```powershell
.\scripts\configure_repository.ps1 -GhPath "C:\Program Files\GitHub CLI\gh.exe"
```
