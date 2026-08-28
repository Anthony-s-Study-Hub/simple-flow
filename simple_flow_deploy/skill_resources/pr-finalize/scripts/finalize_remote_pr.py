from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib.parse import quote


class FinalizationTarget:
    """A deterministically selected delivery target."""

    def __init__(self, *, pr_number: int, issue_numbers: tuple[int, ...], source: str) -> None:
        self.pr_number = pr_number
        self.issue_numbers = issue_numbers
        self.source = source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify and merge one approved Simple Flow GitHub PR.")
    parser.add_argument("--pr", help="Optional pull request number or URL; overrides installed active state.")
    parser.add_argument("--repo", required=True, help="GitHub owner/repository.")
    parser.add_argument("--gh-path", default="gh")
    parser.add_argument("--status-file", default=".simple_tool/status.json")
    parser.add_argument("--delivery-dir", default=".simple_tool/deliveries")
    parser.add_argument("--finalization-dir", default=".simple_tool/finalizations")
    parser.add_argument(
        "--approved",
        action="store_true",
        help="Internal skill authorization; the explicitly invoked skill always supplies this flag.",
    )
    args = parser.parse_args(argv)

    try:
        if not args.approved:
            raise ValueError("Missing explicit PR-Finalize invocation authorization.")
        target = _resolve_target(args.pr, Path(args.status_file), Path(args.delivery_dir))
        ready = _verify_ready(target.pr_number, args.repo, args.gh_path)
        _command(
            [
                args.gh_path,
                "pr",
                "merge",
                str(target.pr_number),
                "--repo",
                args.repo,
                "--merge",
                "--delete-branch",
            ]
        )
        result = _json_command(
            [
                args.gh_path,
                "pr",
                "view",
                str(target.pr_number),
                "--repo",
                args.repo,
                "--json",
                "state,mergedAt,url,headRefName,headRepository,closingIssuesReferences",
            ]
        )
        if result.get("state") != "MERGED" or not result.get("mergedAt"):
            raise ValueError("GitHub did not report a completed merge.")

        issue_numbers = _merge_issue_numbers(
            target.issue_numbers,
            _closing_issue_numbers(ready),
            _closing_issue_numbers(result),
        )
        issues_closed = _ensure_issues_closed(issue_numbers, args.repo, args.gh_path)
        branch_cleanup = _cleanup_head_branch(result, args.repo, args.gh_path)
        pointer_cleanup = _clear_matching_status(
            Path(args.status_file),
            pr_number=target.pr_number,
            issue_numbers=issue_numbers,
        )
        cleanup = {
            "issues_closed": issues_closed,
            "head_branch": branch_cleanup,
            **pointer_cleanup,
        }
        record = {
            "schema": "simple-flow-finalization.v1",
            "pr_number": target.pr_number,
            "pr_url": result["url"],
            "merged_at": result["mergedAt"],
            "target_source": target.source,
            "issue_numbers": list(issue_numbers),
            "cleanup": cleanup,
        }
        _write_finalization(Path(args.finalization_dir), record)
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps({"status": "merged", **record}, indent=2))
    return 0


def _resolve_target(
    explicit_pr: str | None,
    status_path: Path,
    deliveries_dir: Path,
) -> FinalizationTarget:
    status = _load_optional_object(status_path)
    deliveries = _delivery_records(deliveries_dir)
    if explicit_pr:
        pr_number = _pr_number(explicit_pr)
        return FinalizationTarget(
            pr_number=pr_number,
            issue_numbers=_issues_for_pr(pr_number, status, deliveries),
            source="explicit-pr",
        )

    active_pr = _optional_number(status.get("active_pull_request"))
    if active_pr is not None:
        return FinalizationTarget(
            pr_number=active_pr,
            issue_numbers=_issues_for_pr(active_pr, status, deliveries),
            source="active-pull-request",
        )

    active_issue = _optional_number(status.get("active_issue"))
    if active_issue is None:
        raise ValueError("No explicit PR or active delivery is available for finalization.")
    candidates = [record for record in deliveries if record["issue_number"] == active_issue]
    if not candidates:
        raise ValueError(f"No delivery record matches active Issue #{active_issue}.")
    if len(candidates) > 1:
        values = ", ".join(f"#{record['pr_number']}" for record in candidates)
        raise ValueError(f"Active Issue #{active_issue} has multiple delivery records: {values}.")
    candidate = candidates[0]
    return FinalizationTarget(
        pr_number=candidate["pr_number"],
        issue_numbers=(active_issue,),
        source="active-delivery",
    )


def _delivery_records(deliveries_dir: Path) -> list[dict[str, int]]:
    if not deliveries_dir.exists():
        return []
    records: list[dict[str, int]] = []
    for path in sorted(deliveries_dir.glob("*.json")):
        data = _load_object(path)
        issue_number = _optional_number(data.get("issue_number"))
        pr_number = _optional_number(data.get("pr_number"))
        if issue_number is None or pr_number is None:
            raise ValueError(f"Delivery record is missing issue_number or pr_number: {path}")
        records.append({"issue_number": issue_number, "pr_number": pr_number})
    return records


def _issues_for_pr(
    pr_number: int,
    status: dict[str, Any],
    deliveries: list[dict[str, int]],
) -> tuple[int, ...]:
    issues = {record["issue_number"] for record in deliveries if record["pr_number"] == pr_number}
    if _optional_number(status.get("active_pull_request")) == pr_number:
        active_issue = _optional_number(status.get("active_issue"))
        if active_issue is not None:
            issues.add(active_issue)
    return tuple(sorted(issues))


def _verify_ready(pr_number: int, repo: str, gh_path: str) -> dict[str, Any]:
    repository = _json_command([gh_path, "repo", "view", repo, "--json", "defaultBranchRef"])
    default_branch = repository.get("defaultBranchRef", {}).get("name")
    if not default_branch:
        raise ValueError("Could not determine the repository default branch.")
    pr = _json_command(
        [
            gh_path,
            "pr",
            "view",
            str(pr_number),
            "--repo",
            repo,
            "--json",
            "state,isDraft,baseRefName,headRefName,headRepository,closingIssuesReferences",
        ]
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
    return pr


def _ensure_issues_closed(issue_numbers: tuple[int, ...], repo: str, gh_path: str) -> list[int]:
    closed: list[int] = []
    for issue_number in issue_numbers:
        issue = _json_command(
            [gh_path, "issue", "view", str(issue_number), "--repo", repo, "--json", "state"]
        )
        if issue.get("state") == "OPEN":
            _command([gh_path, "issue", "close", str(issue_number), "--repo", repo])
            issue = _json_command(
                [gh_path, "issue", "view", str(issue_number), "--repo", repo, "--json", "state"]
            )
        if issue.get("state") != "CLOSED":
            raise ValueError(f"Associated Issue #{issue_number} is not closed after merge.")
        closed.append(issue_number)
    return closed


def _cleanup_head_branch(pr: dict[str, Any], repo: str, gh_path: str) -> str:
    head = str(pr.get("headRefName") or "")
    head_repository = pr.get("headRepository") or {}
    owner = head_repository.get("nameWithOwner") if isinstance(head_repository, dict) else None
    if not head or owner != repo:
        return "not-applicable"
    default_branch = _json_command([gh_path, "repo", "view", repo, "--json", "defaultBranchRef"])
    if head == default_branch.get("defaultBranchRef", {}).get("name"):
        raise ValueError("Refusing to delete the repository default branch.")
    if _remote_branch_exists(head, repo, gh_path):
        _command(
            [
                gh_path,
                "api",
                "--method",
                "DELETE",
                f"repos/{repo}/git/refs/heads/{quote(head, safe='')}",
            ]
        )
    if _remote_branch_exists(head, repo, gh_path):
        raise ValueError(f"Remote branch {head} still exists after finalization.")
    return "deleted"


def _remote_branch_exists(branch: str, repo: str, gh_path: str) -> bool:
    completed = subprocess.run(
        [gh_path, "api", f"repos/{repo}/git/ref/heads/{quote(branch, safe='')}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode == 0:
        return True
    detail = (completed.stderr or completed.stdout).strip()
    if "404" in detail or "Not Found" in detail:
        return False
    raise ValueError(f"Could not verify remote branch cleanup: {detail}")


def _clear_matching_status(
    status_path: Path,
    *,
    pr_number: int,
    issue_numbers: tuple[int, ...],
) -> dict[str, bool]:
    cleanup = {"active_issue_cleared": False, "active_pull_request_cleared": False}
    if not status_path.exists():
        return cleanup
    status = _load_object(status_path)
    if _optional_number(status.get("active_pull_request")) == pr_number:
        status["active_pull_request"] = None
        cleanup["active_pull_request_cleared"] = True
    if _optional_number(status.get("active_issue")) in set(issue_numbers):
        status["active_issue"] = None
        cleanup["active_issue_cleared"] = True
    status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    return cleanup


def _write_finalization(finalization_dir: Path, record: dict[str, Any]) -> None:
    finalization_dir.mkdir(parents=True, exist_ok=True)
    path = finalization_dir / f"PR-{record['pr_number']}.json"
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def _closing_issue_numbers(pr: dict[str, Any] | None) -> tuple[int, ...]:
    if not isinstance(pr, dict):
        return ()
    references = pr.get("closingIssuesReferences")
    if not isinstance(references, list):
        return ()
    return tuple(
        sorted(
            {
                number
                for reference in references
                if isinstance(reference, dict)
                for number in [_optional_number(reference.get("number"))]
                if number is not None
            }
        )
    )


def _merge_issue_numbers(*groups: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(sorted({number for group in groups for number in group}))


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


def _optional_number(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("Issue and pull request references must be integers.")
    return int(value)


def _load_optional_object(path: Path) -> dict[str, Any]:
    return _load_object(path) if path.exists() else {}


def _load_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


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
