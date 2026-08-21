---
name: simple-flow-start-implement
description: Start or continue formal Simple Flow implementation from an explicitly approved Draft ID and stop at human PR review.
---

# Simple Flow Start-Implement

Owned Stage: Start-Implement

Permission: publish-formal-issue

Human invocation must include an explicit Draft ID:

```text
Start-Implement <Draft ID>
```

The invocation means the named draft passed human review.

## Responsibilities

- Read exactly the specified Canonical Draft.
- Load the draft from `.simple-flow/drafts/<Draft ID>.json`.
- Read the draft Work Type.
- Check whether current conversation context contains one clearly matching
  Review-Triage result.
- Choose the deterministic path.
- Publish or update the formal Issue only through the approved draft data.
- Create the bound branch and draft PR for formal implementation.
- For FEATURE, perform RED, implementation, GREEN, then wait for CI.
- For DOCUMENTATION, update only approved documentation files and do not require
  TDD.
- Stop at Human PR Review.

## Execution

1. Confirm the human invocation includes the exact Draft ID.
2. Run this skill's bundled path-selection script before publishing or updating
   Issues, branches, pull requests, or implementation files:

```powershell
python .codex/skills/start-implement/scripts/select_path.py --draft-id <Draft ID> --drafts-dir .simple-flow/drafts
```

3. If Review-Triage output clearly applies, save that JSON to a temporary file
   and pass it with `--triage-file <triage.json>`. Repeat `--triage-file` for
   multiple candidate triage results.
4. Follow only the returned `path`, `tdd_required`, and `actions`.
5. Stop when the returned `stop_point` is `HUMAN_PR_REVIEW`.

In this source repository, the deploy-time script source of truth is
`simple_flow_deploy/skill_resources/start-implement/scripts/select_path.py`.
Installed projects use the `.codex/skills/start-implement/scripts/select_path.py`
path shown above.

## Boundaries

- Do not guess the latest Draft ID.
- Do not summarize a draft from chat.
- Do not edit an approved draft.
- Do not fill missing draft fields and continue.
- Do not guess when review-triage context is ambiguous.
- Do not merge pull requests.
- Do not invoke or simulate PR-Finalize.

Use the bundled `scripts/select_path.py` entrypoint for deterministic path
selection. Once the pull request is ready for human review, STOP.

