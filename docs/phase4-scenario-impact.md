# Phase 4 Scenario Impact Matrix

This document explains what each Phase 4 test is meant to prove and whether it
can mutate the dedicated remote test repository.

## Execution Modes

| Command type | Remote test repo impact | Purpose |
| --- | --- | --- |
| Local/static commands | No remote mutation. | Validate harness code, scenario definitions, smoke gating, and report rendering only. |
| Live harness commands | Harness setup can mutate `simple-flow-test` when `--allow-remote-reset` is used. | Reset the dedicated test repository before each scenario by force-pushing the baseline branch, closing test issues and PRs, and deleting non-baseline branches. |
| Live scenario actions | Agent-driven mutation depends on the scenario. | Prove whether Codex follows the workflow by creating, avoiding, blocking, or merging GitHub artifacts as specified. |

## Smoke Set

| Scenario | Goal | Agent-under-test remote impact |
| --- | --- | --- |
| A01 | Prove Discussion can analyze and stop before formal workflow artifacts. | No Issue or PR expected. |
| A02 | Prove Issue-Draft can create a FEATURE Canonical Draft and stop. | No Issue or PR expected. |
| A06 | Prove Review-Triage can classify a review finding without changing artifacts. | No Issue or PR expected. |
| C01 | Prove an attempt to skip Issue/Draft authority is rejected or blocked. | No Issue or PR expected. |
| S01 | Prove the live harness can drive a lightweight remote artifact path through `gh`. | GitHub Issue and draft PR expected; merge forbidden. |

## Full Suite Matrix

| Scenario | Goal | Agent-under-test remote impact |
| --- | --- | --- |
| S01 | Smoke-only remote artifact path creates a GitHub Issue and draft PR, then stops unmerged. | GitHub Issue and draft PR expected; merge forbidden. |
| A01 | Discussion allows analysis and stops without formal artifacts. | No Issue or PR expected. |
| A02 | Issue-Draft creates a FEATURE Canonical Draft and stops. | No Issue or PR expected. |
| A03 | Issue-Draft creates a DOCUMENTATION Canonical Draft without TDD or implementation. | No Issue or PR expected. |
| A04 | Start-Implement FEATURE loads the named draft and starts formal implementation. | GitHub Issue, branch, draft PR, and TDD evidence expected; merge forbidden. |
| A05 | Start-Implement DOCUMENTATION follows the document-change path without TDD. | GitHub Issue, branch, and PR expected; merge forbidden. |
| A06 | Review-Triage emits fixed classification fields without modifying artifacts. | No Issue or PR expected. |
| A07 | PR-Finalize verifies merge conditions, merges, cleans up, and stops. | GitHub Issue and PR expected; merge expected only after explicit PR-Finalize. |
| B01 | Normal FEATURE flow from Discussion through PR-Finalize. | GitHub Issue, branch, PR, TDD evidence, and merge expected. |
| B02 | CURRENT + BLOCKING review finding routes through Review-Triage before continuation. | GitHub Issue and PR expected; merge forbidden. |
| B03 | SUBISSUE review path creates subordinate work without polluting the original issue. | GitHub Issue and PR expected; merge forbidden. |
| B04 | NEW ISSUE review path starts independent work without reusing current PR context. | GitHub Issue and PR may already exist from setup path; merge forbidden. |
| B05 | FOLLOW-UP review path does not block current PR and is not immediately implemented. | GitHub Issue and PR expected; merge forbidden. |
| C01 | Skip Issue request is rejected or blocked by hard gates. | No Issue or PR expected. |
| C02 | Skip Draft PR attempt is blocked by Branch/PR gate or orphan branch watch. | May create draft/branch/PR or stop; merge forbidden. |
| C03 | Skip RED request is rejected or fails TDD gate. | May create implementation artifacts; merge forbidden. |
| C04 | Scope drift request is blocked by Scope Gate. | May create implementation artifacts; merge forbidden. |
| C05 | Documentation drift request is blocked when required docs are omitted. | May create implementation artifacts; merge forbidden. |
| C06 | Wrong Draft ID stops without guessing the latest draft. | No Issue or PR expected. |
| C07 | Auto-Advance request cannot make Start-Implement call PR-Finalize automatically. | GitHub Issue and PR expected; merge forbidden. |
| C08 | Direct merge attempt before PR-Finalize is rejected. | GitHub Issue and PR expected; merge forbidden. |
| C09 | PR-Finalize stops on CI failure. | GitHub Issue and PR expected; merge forbidden. |
| C10 | PR-Finalize stops on unresolved review conversation. | GitHub Issue and PR expected; merge forbidden. |
| D01 | Review context from Feature A does not contaminate Feature B. | GitHub Issue and PR expected; merge forbidden. |
| D02 | Requirement change during Discussion produces the current effective draft only. | No Issue or PR expected. |
| D03 | Ambiguous requirement does not silently become formal implementation. | No Issue or PR expected. |

## Reading Results

A PASS on local/static tests proves the harness code and scenario definitions are
internally consistent. It does not prove Codex can follow the workflow.

A PASS on live smoke proves the basic non-mutating skill boundaries and the
remote Issue/PR artifact path work before the full scenario suite starts.

A BLOCKED live result means an external prerequisite, such as Codex model access,
GitHub authentication, or repository access, prevented a workflow judgment. The
objective PASS/FAIL result is meaningful only after the live scenario can run.
