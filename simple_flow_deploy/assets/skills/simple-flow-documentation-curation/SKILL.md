---
name: simple-flow-documentation-curation
description: Curate Simple Flow Issue, PR, review, and merge history into structured baseline update proposals and a DOCUMENTATION Canonical Draft, then stop.
---

# Simple Flow Documentation-Curation

Owned Stage: Documentation-Curation

Permission: generate-documentation-curation-draft

Use this skill only when the human asks to curate project history into baseline
documentation update proposals.

## Responsibilities

- Read normalized history collected since the last committed curation cursor.
- Group related Issue / PR / review evidence into technical decision proposals.
- Classify decisions as FINAL, SUPERSEDED, INTERMEDIATE, ABANDONED, FOLLOW_UP,
  IMPLEMENTATION_ONLY, or UNRESOLVED.
- Include only baseline-relevant FINAL decisions, plus required SUPERSEDED
  entries, in proposed baseline operations.
- Produce Documentation Findings for unresolved or contradictory history.
- Propose new Component Baselines only when there is a durable responsibility
  boundary.
- Generate one DOCUMENTATION Canonical Draft and STOP.

## Execution

1. Collect or receive the normalized history package. The agent must not search
   GitHub history manually when deterministic collection output is available.
2. Read that normalized package and perform only the semantic analysis:
   decision grouping, classification, baseline relevance, conflicts, and new
   component judgement.
3. Save the semantic analysis as JSON with these top-level fields:
   `decisions`, `findings`, `new_components`, and `affected_project_documents`.
4. Run this skill's bundled deterministic renderer:

```powershell
python .codex/skills/documentation-curation/scripts/curate_documentation.py --history-package <history.json> --analysis <analysis.json> --drafts-dir .simple-flow/drafts --output-dir .simple-flow/documentation-curation
```

5. Report the returned `draft_id`, `draft_json`, `draft_markdown`,
   `pending_cursor`, and `stop_point`, then STOP.

In this source repository, the deploy-time script source of truth is
`simple_flow_deploy/skill_resources/documentation-curation/scripts/curate_documentation.py`.
Installed projects use the `.codex/skills/documentation-curation/scripts/curate_documentation.py`
path shown above.

## Decision Proposal

Each proposal is an independent review unit with these fields:

- Decision ID
- Component
- Proposed Classification
- Decision
- Short Reason
- Constraint / Consequence
- Supersedes
- Exact References
- Affected Baseline Section
- Proposed Baseline Action

FINAL decisions must have at least one exact valid reference. If evidence is
insufficient, classify the proposal as UNRESOLVED and do not propose a baseline
write.

## Documentation Finding

Each finding is an independent review unit with these fields:

- Finding ID
- Component
- Type
- Conflict
- Why It Matters
- Exact References
- Question
- Affected Baseline Section
- Blocking Impact

Unresolved blocking findings must block the affected baseline section until a
human answers the question. Unresolved nonblocking findings may accompany other
determinate proposals.

## Boundaries

- Do not directly modify formal Baseline documents.
- Do not create or update GitHub Issues.
- Do not create branches or pull requests.
- Do not invoke or simulate Start-Implement.
- Do not modify code, configuration, or scripts as part of curation output.
- Do not invoke PR-Finalize.
- Do not merge.
- Do not advance the committed curation cursor. Only report the pending cursor.

The only terminal output artifact is a DOCUMENTATION Canonical Draft. After
reporting that Draft ID, STOP.
