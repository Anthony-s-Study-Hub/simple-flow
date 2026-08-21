from __future__ import annotations

from scripts.orphan_branch_watch import _normalize_remote_branch_names


def test_normalize_remote_branch_names_ignores_origin_head_aliases() -> None:
    assert _normalize_remote_branch_names(
        [
            "origin",
            "origin/HEAD",
            "origin/main",
            "origin/feature/998-orphan-watch-probe",
        ]
    ) == ["main", "feature/998-orphan-watch-probe"]
