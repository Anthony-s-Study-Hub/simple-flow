# Simple Flow Agent Rules

These rules apply to every Codex skill and every agent working in this
repository.

## Default Deny

Default Deny is the global rule: if the current skill has not explicitly
authorized an action, the agent must not perform it. If the current skill has not explicitly authorized an action, that action is forbidden.

## Conversation-First Stage Confirmation

Treat every user message as discussion by default. Do not mention skills.
Do not ask for confirmation while the plan is incomplete or exploratory. Continue the
conversation until the objective, scope, and next state-changing stage are
clear enough to act on.

When that stage is ready, briefly propose one specific action and its intended
effect, then ask for confirmation once. The original request does not itself authorize the stage.
Proceed only after a later, unambiguous user confirmation
that still matches the proposed action. If the scope changes materially, return
to discussion and make a new proposal when it is ready.

One confirmation is single-use and covers all internal work owned by that stage.
Do not ask again for its TDD, branch, Issue, draft PR, CI, or other
internal steps. After the stage completes, return to discussion until a later
natural boundary requires another proposed action and confirmation.

Before confirmation, do not create or change Canonical Drafts,
`.simple_tool/` transition files, Issues, branches, pull requests, implementation
code, or documentation content. After confirmation, invoke the owning skill
implicitly; the user does not need to name a skill.

Every skill must stop after completing its owned stage. A skill must not call or simulate the next stage, even when the next step seems obvious.

Only Issue-Draft may create or replace a Canonical Draft. Documentation-Curation
retains its separate authority to create its dedicated DOCUMENTATION Canonical
Draft and its own curation outputs.

Only Documentation-Curation may curate technical history into Decision
Proposals, Documentation Findings, New Component Proposals, and a
DOCUMENTATION Canonical Draft.

Only Start-Implement may publish or update formal Issues, create implementation
branches, create draft pull requests, mark an implementation PR ready for
review, or continue formal implementation from an approved Canonical Draft.

Only PR-Finalize may merge pull requests after explicit human invocation.

Review-Triage may create only its own decision files under `.simple_tool/triage/`.
It must not modify drafts, Issues, code, branches, pull requests, or review threads.

Documentation-Curation must not directly modify formal Baselines, create Issues,
create branches, create pull requests, invoke Start-Implement, modify code or
configuration, invoke PR-Finalize, or merge.

Only the owning skill may change transition files under `.simple_tool/`:

- Issue-Draft: `.simple_tool/drafts/` and the active Draft pointer in status.
- Review-Triage: `.simple_tool/triage/`.
- Start-Implement: `.simple_tool/deliveries/` and active Issue/PR pointers in status.
- Documentation-Curation: its dedicated curation outputs and documentation Draft.
- PR-Finalize: `.simple_tool/finalizations/` and may conditionally clear matching
  active Issue/PR pointers in status after a verified merge.

No other skill or agent may create or change Canonical Drafts, implementation
artifacts, or `.simple_tool/` transition files.

Start-Implement must not merge pull requests.

Agents must not bypass Issue, Branch, Pull Request, or CI gates. Phase 1 remains
the hard gate for objective validation.

If PR Review finds a new problem, the agent must go through Review-Triage before fixes. Direct review finding to code fix is forbidden.

Concrete schemas, script commands, and stage-specific workflow details belong in
the owning skill, not in this shared file.
