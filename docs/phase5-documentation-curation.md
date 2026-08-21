# Phase 5 Documentation Curation

Phase 5 adds the Documentation-Curation skill and deterministic helper package.
The skill curates Issue, PR, review, merge, and reference history into
structured baseline update proposals.

## Boundary

Documentation-Curation ends at one artifact:

```text
DOCUMENTATION Canonical Draft
```

It does not modify formal baselines, create Issues, create branches, create PRs,
invoke Start-Implement, invoke PR-Finalize, or merge. The generated draft enters
the existing DOCUMENTATION path only after human review.

## Deterministic Helpers

The `simple_flow_documentation_curation` package owns mechanical behavior:

- history normalization
- objective Issue / PR relationship resolution
- curation cursor calculation and pending cursor persistence
- component mapping
- baseline schema validation
- structural conflict checks
- exact Issue, PR, review, comment, commit, and file-line reference validation
- fixed patch operation planning
- deterministic DOCUMENTATION draft rendering
- version and Last Updated helpers

The collector applies an `Updated At` plus stable-ID cursor boundary. A pending
cursor is written for the current curation run, but the committed cursor advances
only after the corresponding documentation PR is merged.

The agent only performs semantic grouping, classification, baseline relevance
judgement, conflict wording, and new component judgement.

## Installed Skill Entrypoint

Installed projects run:

```powershell
python .codex/skills/documentation-curation/scripts/curate_documentation.py --history-package <history.json> --analysis <analysis.json> --drafts-dir .simple-flow/drafts --output-dir .simple-flow/documentation-curation
```

The script validates references and analysis structure, creates a
DOCUMENTATION draft through the existing draft store, records a pending curation
cursor, and reports `DOCUMENTATION_DRAFT_CREATED`.
