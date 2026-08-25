---
name: simple-flow-start-implement
description: Start or continue formal Simple Flow implementation from an approved Canonical Draft and stop at human PR review.
---

# Simple Flow Start-Implement

Owned Stage: Start-Implement

Permission: publish-formal-issue

Human invocation may include a Draft ID, but does not need to repeat one that is
already clear from the conversation:

```text
Start-Implement [Draft ID]
```

The invocation means the selected draft passed human review.

## Responsibilities

- Resolve the approved Canonical Draft from the invocation and conversation.
- Prefer an explicit Draft ID when supplied. Otherwise use the most recent
  clearly relevant Canonical Draft produced or reviewed in the current
  conversation.
- Ask for an explicit Draft ID only when multiple plausible drafts remain and
  the conversation does not make the implementation target clear.
- Read exactly the selected Canonical Draft.
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

1. Resolve one approved Draft ID. If an explicitly supplied Draft ID does not
   exist, report that error rather than substituting another draft. If no draft
   is available from the invocation or conversation, report the missing
   prerequisite and STOP.
2. Run this skill's bundled path-selection script before publishing or updating
   Issues, branches, pull requests, or implementation files:

```powershell
python .codex/skills/start-implement/scripts/select_path.py --draft-id <Draft ID> --drafts-dir .simple-flow/drafts
```

3. If Review-Triage output clearly applies, save that JSON to a temporary file
   and pass it with `--triage-file <triage.json>`. Repeat `--triage-file` for
   multiple candidate triage results.
4. Follow only the returned `path`, `tdd_required`, and `actions`.
5. For a `DOCUMENTATION_NORMAL` path where the approved draft Change is an
   append-only documentation instruction, use the bundled documentation helper
   instead of manually recreating the GitHub Issue, branch, commit, push, and
   draft PR steps:

   In a cloned developer repository, derive `--repo` from
   `git remote get-url origin`. Use `gh` from `PATH` unless the environment
   exposes a different executable. Do not ask the developer for either value
   when they are discoverable locally.

```powershell
python .codex/skills/start-implement/scripts/start_documentation.py --draft-id <Draft ID> --drafts-dir .simple-flow/drafts --repo <origin URL> --gh-path gh
```

6. Opening the approved formal Issue and draft pull request is not a new human
   approval boundary. Do not pause for another approval there; continue the
   selected implementation path, tests, and CI checks until the completed pull
   request is ready for human review.
7. Stop when the returned `stop_point` is `HUMAN_PR_REVIEW`, or report an
   objective blocker that prevents reaching it.

In this source repository, the deploy-time script source of truth is
`simple_flow_deploy/skill_resources/start-implement/scripts/select_path.py`.
Installed projects use the `.codex/skills/start-implement/scripts/select_path.py`
path shown above.
The deploy-time source of truth for the documentation helper is
`simple_flow_deploy/skill_resources/start-implement/scripts/start_documentation.py`.

## Boundaries

- Do not choose among multiple plausible drafts when conversation context is
  ambiguous.
- Do not summarize a draft from chat.
- Do not edit an approved draft.
- Do not fill missing draft fields and continue.
- Do not guess when review-triage context is ambiguous.
- Do not merge pull requests.
- Do not invoke or simulate PR-Finalize.

Use the bundled `scripts/select_path.py` entrypoint for deterministic path
selection. Once the pull request is ready for human review, STOP.

