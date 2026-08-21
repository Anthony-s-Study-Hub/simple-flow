from __future__ import annotations

import argparse
import json
import subprocess
import sys

from simple_flow_gates.orphan import BranchState, find_orphan_branches


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--gh-path", default="gh")
    args = parser.parse_args(argv)

    branches = _load_branch_states(args.repo, args.base, args.gh_path)
    orphans = find_orphan_branches(branches)
    if orphans:
        for branch in orphans:
            print(
                f"orphan branch: {branch.name} "
                f"({branch.commits_ahead} commit(s) ahead, no open PR)",
                file=sys.stderr,
            )
        return 1
    print("Orphan Branch Watch PASS")
    return 0


def _load_branch_states(repo: str, base: str, gh_path: str) -> list[BranchState]:
    _fetch_all()
    remote_branches = _remote_branch_names()
    open_pr_heads = _open_pr_heads(repo, gh_path)
    states: list[BranchState] = []
    for branch in remote_branches:
        commits_ahead = _commits_ahead(base, f"origin/{branch}")
        states.append(
            BranchState(
                name=branch,
                commits_ahead=commits_ahead,
                has_open_pr=branch in open_pr_heads,
            )
        )
    return states


def _fetch_all() -> None:
    subprocess.run(["git", "fetch", "--all", "--prune"], check=True)


def _remote_branch_names() -> list[str]:
    result = subprocess.run(
        ["git", "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin"],
        check=True,
        capture_output=True,
        text=True,
    )
    return _normalize_remote_branch_names(result.stdout.splitlines())


def _normalize_remote_branch_names(refs: list[str]) -> list[str]:
    branches = []
    for ref in refs:
        name = ref.strip()
        if not name or name in {"origin", "origin/HEAD"}:
            continue
        branches.append(name.removeprefix("origin/"))
    return branches


def _open_pr_heads(repo: str, gh_path: str) -> set[str]:
    result = subprocess.run(
        [
            gh_path,
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--json",
            "headRefName",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return {item["headRefName"] for item in json.loads(result.stdout)}


def _commits_ahead(base: str, branch: str) -> int:
    result = subprocess.run(
        ["git", "rev-list", "--count", f"{base}..{branch}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return int(result.stdout.strip() or "0")


if __name__ == "__main__":
    raise SystemExit(main())
