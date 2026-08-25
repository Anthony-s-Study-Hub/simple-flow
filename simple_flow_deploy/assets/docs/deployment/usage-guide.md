# Simple Flow Usage Guide

Use the six skills as human-invoked stage boundaries.

Install or upgrade this workflow only with the versioned public GitHub
repository command documented by Simple Flow. Installed skills come from the
package's `simple_flow_deploy/assets/skills` SSOT; local checkouts and ignored
`build/` output are not deployment sources.

## Normal FEATURE

1. Use Discussion to explore the request. It stops after summarizing consensus.
2. Use Issue-Draft to create a Canonical Draft. It runs its bundled
   `scripts/create_draft.py` entrypoint and stops after reporting the Draft ID.
3. Review the draft as a human.
4. Use Start-Implement. When the approved draft is clear from the conversation,
   it selects that draft without requiring the Draft ID again. It asks for an
   explicit Draft ID only if multiple drafts remain plausible. After opening the
   Issue and draft PR, it continues implementation and CI without another
   approval pause, then stops at Human PR Review.
5. Review the pull request as a human.
6. Use PR-Finalize with the accepted PR. It runs its bundled
   `scripts/check_pre_merge.py` entrypoint and merges only after objective
   checks pass.

## Review-Triage Flow

When PR Review finds a problem, use Review-Triage. It runs its bundled
`scripts/classify_finding.py` entrypoint, infers a clear current Issue and PR
from the conversation and repository, classifies the finding, and stops. The
user only needs to identify the target when multiple candidates are genuinely
ambiguous. Then use Issue-Draft for the next approved change and Start-Implement
for the resulting approved draft.

## DOCUMENTATION

Use Issue-Draft to create a DOCUMENTATION draft. Start-Implement updates only
approved documentation files and does not require TDD. PR-Finalize is still the
only merge entry point after human review.

## Documentation-Curation

Use Documentation-Curation when project history needs to be curated into
baseline update proposals. It reads deterministic history input, produces
Decision Proposals, Documentation Findings, New Component Proposals, and one
DOCUMENTATION Canonical Draft, then stops. The draft must be reviewed by a
human before the existing DOCUMENTATION flow begins with Start-Implement.

