from __future__ import annotations

import pytest


ROADMAP_TARGETS = {"PHASE_1_GOVERNANCE"}


@pytest.fixture
def roadmap_targets() -> set[str]:
    return ROADMAP_TARGETS


def feature_issue_body(
    *,
    scope: str = "- simple_flow_gates/\n- tests/\n- .simple-flow/tdd-evidence/*.json",
    docs: str = "None",
    roadmap: str = "PHASE_1_GOVERNANCE",
) -> str:
    return f"""Type: FEATURE

## Summary

Add deterministic phase 1 gates.

## Requirements

- Validate contracts.

## Acceptance Criteria

- Invalid contracts fail.

## Scope

{scope}

## Out of Scope

Agent skills.

## Documentation Impact

{docs}

## Roadmap Target

{roadmap}
"""


def project_change_issue_body(
    *,
    docs: str = "- docs/phase1-governance.md",
) -> str:
    return f"""Type: PROJECT_CHANGE

## Change

Update the project baseline.

## Reason

The governance policy changed.

## Impact

Future development must follow the updated policy.

## Supersedes

None

## Affected Project Documents

{docs}

## Source PR / Decision Context

#1
"""


def pr_body(issue: int = 123) -> str:
    return f"""## Linked Issue

Closes #{issue}

## Implementation Summary

Implemented deterministic gates.

## Acceptance Criteria Evidence

Tests pass.

## Changed Files / Scope

Only declared files changed.

## Documentation Changes

None

## Important Technical Decisions

Kept validators deterministic.

## Known Limitations

None
"""

