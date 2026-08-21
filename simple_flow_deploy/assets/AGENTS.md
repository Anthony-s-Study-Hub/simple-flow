# Simple Flow Agent Rules

These rules apply to every Codex skill and every agent working in this
repository.

## Default Deny

Default Deny is the global rule: if the current skill has not explicitly
authorized an action, the agent must not perform it. If the current skill has not explicitly authorized an action, that action is forbidden.

Every skill must stop after completing its owned stage. A skill must not call or simulate the next stage, even when the next step seems obvious.

Only Issue-Draft may generate a Canonical Draft.

Only Documentation-Curation may curate technical history into Decision
Proposals, Documentation Findings, New Component Proposals, and a
DOCUMENTATION Canonical Draft.

Only Start-Implement may publish or update formal Issues, create implementation
branches, create draft pull requests, or continue formal implementation from an
approved Draft ID.

Only PR-Finalize may merge pull requests after explicit human review acceptance.

Review-Triage must not modify issues or code.

Documentation-Curation must not directly modify formal Baselines, create Issues,
create branches, create pull requests, invoke Start-Implement, modify code or
configuration, invoke PR-Finalize, or merge.

Discussion must not generate formal drafts, publish issues, create branches,
create pull requests, or modify formal implementation.

Start-Implement must not merge pull requests.

Agents must not bypass Issue, Branch, Pull Request, or CI gates. Phase 1 remains
the hard gate for objective validation.

If PR Review finds a new problem, the agent must go through Review-Triage before fixes. Direct review finding to code fix is forbidden.

Concrete schemas, script commands, and stage-specific workflow details belong in
the owning skill, not in this shared file.
