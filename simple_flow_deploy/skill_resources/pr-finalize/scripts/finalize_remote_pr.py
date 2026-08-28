from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify and merge one approved Simple Flow GitHub PR.")
    parser.add_argument("--pr", required=True, help="Approved pull request number or URL.")
    parser.add_argument("--repo", required=True, help="GitHub owner/repository.")
    parser.add_argument("--gh-path", default="gh")
    parser.add_argument(
        "--approved",
        action="store_true",
        help="Set only after the user explicitly approved this exact PR for merge.",
    )
    args = parser.parse_args(argv)

    try:
        if not args.approved:
            raise ValueError("Missing explicit user approval for this pull request.")
        pr_number = _pr_number(args.pr)
        _verify_ready(pr_number, args.repo, args.gh_path)
        _command([args.gh_path, "pr", "merge", str(pr_number), "--repo", args.repo, "--delete-branch"])
        result = _json_command(
            [args.gh_path, "pr", "view", str(pr_number), "--repo", args.repo, "--json", "state,mergedAt,url"]
        )
        if result.get("state") != "MERGED" or not result.get("mergedAt"):
            raise ValueError("GitHub did not report a completed merge.")
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps({"status": "merged", "pr_number": pr_number, "url": result["url"]}, indent=2))
    return 0


def _verify_ready(pr_number: int, repo: str, gh_path: str) -> None:
    repository = _json_command([gh_path, "repo", "view", repo, "--json", "defaultBranchRef"])
    default_branch = repository.get("defaultBranchRef", {}).get("name")
    if not default_branch:
        raise ValueError("Could not determine the repository default branch.")
    pr = _json_command(
        [gh_path, "pr", "view", str(pr_number), "--repo", repo, "--json", "state,isDraft,baseRefName"]
    )
    if pr.get("state") != "OPEN":
        raise ValueError("Pull request is not open.")
    if pr.get("isDraft"):
        raise ValueError("Pull request is still a draft.")
    if pr.get("baseRefName") != default_branch:
        raise ValueError("Pull request does not target the repository default branch.")
    required = _required_checks(repo, default_branch, gh_path)
    observed = {
        item["name"]: item["state"]
        for item in _json_command(
            [gh_path, "pr", "checks", str(pr_number), "--repo", repo, "--json", "name,state"]
        )
    }
    failing = sorted(name for name in required if observed.get(name) != "SUCCESS")
    if failing:
        raise ValueError("Required CI checks are not successful: " + ", ".join(failing))
    if _unresolved_review_threads(pr_number, repo, gh_path):
        raise ValueError("Pull request has unresolved review threads.")


def _required_checks(repo: str, branch: str, gh_path: str) -> set[str]:
    raw = _json_command(
        [gh_path, "api", f"repos/{repo}/branches/{branch}/protection/required_status_checks"]
    )
    names = {str(item["context"]) for item in raw.get("checks", [])}
    names.update(str(name) for name in raw.get("contexts", []))
    if not names:
        raise ValueError("No required CI checks are configured for the target branch.")
    return names


def _unresolved_review_threads(pr_number: int, repo: str, gh_path: str) -> bool:
    owner, name = repo.split("/", 1)
    query = (
        "query($owner:String!, $name:String!, $number:Int!) { "
        "repository(owner:$owner, name:$name) { pullRequest(number:$number) { "
        "reviewThreads(first:100) { nodes { isResolved } } } } }"
    )
    raw = _json_command(
        [
            gh_path,
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={name}",
            "-F",
            f"number={pr_number}",
        ]
    )
    threads = raw["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
    return any(not thread["isResolved"] for thread in threads)


def _pr_number(value: str) -> int:
    tail = value.rstrip("/").rsplit("/", 1)[-1]
    return int(tail)


def _json_command(command: list[str]):
    return json.loads(_command(command))


def _command(command: list[str]) -> str:
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()
        raise ValueError(f"Command failed ({' '.join(command[:3])}): {detail}")
    return (completed.stdout or completed.stderr).strip()


if __name__ == "__main__":
    raise SystemExit(main())
