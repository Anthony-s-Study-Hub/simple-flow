# GitHub Setup Guide

For a public repository, configure:

- Pull requests required for `main`.
- Required status checks: `pr-contract`, `linked-issue-contract`,
  `scope-governance`, `documentation-impact`, `tdd-evidence-order`,
  `tdd-red-replay`, `tdd-green-replay`, and `current-head-tests`.
- Strict required checks.
- Review conversation resolution required.
- Force pushes disabled.
- Branch deletion disabled on `main`.
- Delete merged head branches enabled.
- Auto-merge disabled by default.

Use the installed `scripts/configure_repository.ps1` helper as the deterministic
starting point, then connect any project-specific GitHub Projects automation.

