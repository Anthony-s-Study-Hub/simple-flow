# Simple Flow Usage Guide

Use the five skills as human-invoked stage boundaries.

## Normal FEATURE

1. Use Discussion to explore the request. It stops after summarizing consensus.
2. Use Issue-Draft to create a Canonical Draft. It runs its bundled
   `scripts/create_draft.py` entrypoint and stops after reporting the Draft ID.
3. Review the draft as a human.
4. Use Start-Implement with the approved Draft ID. It runs its bundled
   `scripts/select_path.py` entrypoint and stops at Human PR Review.
5. Review the pull request as a human.
6. Use PR-Finalize with the accepted PR. It runs its bundled
   `scripts/check_pre_merge.py` entrypoint and merges only after objective
   checks pass.

## Review-Triage Flow

When PR Review finds a problem, use Review-Triage. It runs its bundled
`scripts/classify_finding.py` entrypoint, classifies the finding, and stops.
Then use Issue-Draft for the next approved change and Start-Implement for the
specified Draft ID.

## DOCUMENTATION

Use Issue-Draft to create a DOCUMENTATION draft. Start-Implement updates only
approved documentation files and does not require TDD. PR-Finalize is still the
only merge entry point after human review.

