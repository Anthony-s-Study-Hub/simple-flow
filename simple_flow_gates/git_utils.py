from __future__ import annotations

import subprocess


def changed_files(base_ref: str = "origin/main") -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def commit_history(base_ref: str = "origin/main") -> list[str]:
    result = subprocess.run(
        ["git", "rev-list", "--reverse", f"{base_ref}..HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]

