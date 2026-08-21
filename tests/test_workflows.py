from __future__ import annotations

from pathlib import Path


def test_orphan_branch_watch_passes_gh_token_to_detector() -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "orphan-branch-watch.yml"
    ).read_text(encoding="utf-8")

    assert "GH_TOKEN: ${{ github.token }}" in workflow
    assert "python -m scripts.orphan_branch_watch" in workflow


def test_phase1_pr_gate_uses_stable_event_base_sha() -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "phase1-gates.yml"
    ).read_text(encoding="utf-8")

    assert '--base-ref "${{ github.event.pull_request.base.sha }}"' in workflow
