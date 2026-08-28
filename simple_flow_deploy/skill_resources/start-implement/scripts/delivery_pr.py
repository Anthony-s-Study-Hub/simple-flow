from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


class GitHubGateway:
    def __init__(self, *, repo: str, base_branch: str, draft_body: Path, gh_path: str) -> None:
        self.repo = repo
        self.base_branch = base_branch
        self.draft_body = draft_body
        self.gh_path = gh_path

    def ensure_issue(self, target) -> tuple[int, str]:
        matches = _json_command(
            [
                self.gh_path,
                "issue",
                "list",
                "--repo",
                self.repo,
                "--state",
                "all",
                "--search",
                target.summary,
                "--json",
                "number,url,title",
            ]
        )
        exact = [item for item in matches if item.get("title") == target.summary]
        if len(exact) > 1:
            raise ValueError(f"Multiple matching Issues exist for selected draft {target.draft_id}.")
        if exact:
            return int(exact[0]["number"]), str(exact[0]["url"])
        url = _command(
            [
                self.gh_path,
                "issue",
                "create",
                "--repo",
                self.repo,
                "--title",
                target.summary,
                "--body-file",
                str(self.draft_body),
            ]
        )
        return _number(url, "issues"), url

    def ensure_branch(self, target, issue_number: int) -> str:
        prefix = "documentation" if target.work_type == "DOCUMENTATION" else "feature"
        branch = f"{prefix}/{issue_number}-{_slug(target.summary)}"
        _switch_branch(branch)
        if _command(["git", "rev-list", "--count", f"origin/{self.base_branch}..HEAD"]) == "0":
            _command(
                ["git", "commit", "--allow-empty", "-m", f"chore: open delivery for #{issue_number}"],
            )
        _command(["git", "push", "--set-upstream", "origin", branch])
        return branch

    def ensure_draft_pr(self, target, issue_number: int, branch: str) -> tuple[int, str]:
        existing = _json_command(
            [
                self.gh_path,
                "pr",
                "list",
                "--repo",
                self.repo,
                "--head",
                branch,
                "--state",
                "open",
                "--json",
                "number,url,isDraft",
            ]
        )
        if len(existing) > 1:
            raise ValueError(f"Multiple open PRs exist for branch {branch}.")
        if existing:
            if not existing[0].get("isDraft", False):
                raise ValueError(f"Existing PR for {branch} is already ready for review.")
            return int(existing[0]["number"]), str(existing[0]["url"])
        body = _pr_body(issue_number, target)
        with tempfile.TemporaryDirectory(prefix="simple-flow-delivery-") as temp_dir:
            body_path = Path(temp_dir) / "pr-body.md"
            body_path.write_text(body, encoding="utf-8")
            url = _command(
                [
                    self.gh_path,
                    "pr",
                    "create",
                    "--repo",
                    self.repo,
                    "--base",
                    self.base_branch,
                    "--head",
                    branch,
                    "--title",
                    target.summary,
                    "--body-file",
                    str(body_path),
                    "--draft",
                ]
            )
        return _number(url, "pull"), url

    def review_state(self, record) -> tuple[bool, tuple[str, ...]]:
        pr = _json_command(
            [
                self.gh_path,
                "pr",
                "view",
                str(record.pr_number),
                "--repo",
                self.repo,
                "--json",
                "state,isDraft,baseRefName",
            ]
        )
        if pr.get("state") != "OPEN" or pr.get("baseRefName") != record.base_branch:
            return False, ("PR is not open against the required base branch",)
        required = _required_check_names(self.repo, record.base_branch, self.gh_path)
        observed = {
            item["name"]: item["state"]
            for item in _json_command(
                [
                    self.gh_path,
                    "pr",
                    "checks",
                    str(record.pr_number),
                    "--repo",
                    self.repo,
                    "--json",
                    "name,state",
                ]
            )
        }
        blocked = tuple(sorted(name for name in required if observed.get(name) != "SUCCESS"))
        return not blocked, blocked

    def mark_ready(self, record) -> None:
        _command([self.gh_path, "pr", "ready", str(record.pr_number), "--repo", self.repo])
        _command(
            [
                self.gh_path,
                "pr",
                "checks",
                str(record.pr_number),
                "--repo",
                self.repo,
                "--required",
                "--watch",
            ]
        )


def main(argv: list[str] | None = None) -> int:
    _add_repo_root_to_path()
    from simple_flow_agent.delivery import (
        DeliveryRecord,
        DeliveryTarget,
        prepare_delivery,
        ready_for_review,
    )
    from simple_flow_agent.drafts import DraftStore

    parser = argparse.ArgumentParser(description="Open or ready a deterministic Simple Flow delivery PR.")
    parser.add_argument("command", choices=["open", "ready"])
    parser.add_argument("--plan", required=True, help="JSON output from plan_implementation.py")
    parser.add_argument("--drafts-dir", default=".simple_tool/drafts")
    parser.add_argument("--delivery-dir", default=".simple_tool/deliveries")
    parser.add_argument("--status-file", default=".simple_tool/status.json")
    parser.add_argument("--repo", required=True, help="GitHub owner/repository")
    parser.add_argument("--base", default="main")
    parser.add_argument("--gh-path", default="gh")
    args = parser.parse_args(argv)

    try:
        plan = _load_plan(Path(args.plan))
        draft = DraftStore(args.drafts_dir).read(str(plan["draft_id"]))
        target = DeliveryTarget(
            draft_id=draft.draft_id,
            work_type=str(plan["work_type"]),
            summary=str(plan["summary"]),
            route=str(plan["route"]),
            repository=args.repo,
            base_branch=args.base,
            source_issue=draft.source_issue,
            source_pr=draft.source_pr,
        )
        gateway = GitHubGateway(
            repo=args.repo,
            base_branch=args.base,
            draft_body=Path(args.drafts_dir) / f"{draft.draft_id}.md",
            gh_path=args.gh_path,
        )
        record_path = Path(args.delivery_dir) / f"{draft.draft_id}.json"
        existing = DeliveryRecord.from_json_data(_load_json(record_path)) if record_path.exists() else None
        if args.command == "open":
            record = prepare_delivery(target, gateway=gateway, existing=existing)
        else:
            if existing is None:
                raise ValueError("Delivery record is missing; run delivery_pr.py open first.")
            record = ready_for_review(existing, gateway=gateway)
        _save_json(record_path, record.to_json_data())
        _record_status(Path(args.status_file), record)
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps({"status": "ok", **record.to_json_data()}, indent=2))
    return 0


def _load_plan(path: Path) -> dict[str, Any]:
    raw = _load_json(path)
    if raw.get("status") != "ready":
        raise ValueError("Implementation plan is not ready.")
    for name in ("draft_id", "work_type", "summary", "route"):
        if not raw.get(name):
            raise ValueError(f"Implementation plan is missing {name}.")
    return raw


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return raw


def _save_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _record_status(path: Path, record) -> None:
    if not path.exists():
        return
    status = _load_json(path)
    status.update({"active_issue": record.issue_number, "active_pull_request": record.pr_number})
    _save_json(path, status)


def _required_check_names(repo: str, branch: str, gh_path: str) -> set[str]:
    raw = _json_command(
        [gh_path, "api", f"repos/{repo}/branches/{branch}/protection/required_status_checks"]
    )
    names = {str(item["context"]) for item in raw.get("checks", [])}
    names.update(str(name) for name in raw.get("contexts", []))
    if not names:
        raise ValueError("No required CI checks are configured for the target branch.")
    return names


def _switch_branch(branch: str) -> None:
    completed = subprocess.run(["git", "switch", branch], capture_output=True, text=True)
    if completed.returncode == 0:
        return
    remote = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}"],
        capture_output=True,
        text=True,
    )
    if remote.returncode == 0:
        _command(["git", "switch", "--track", "-c", branch, f"origin/{branch}"])
        return
    _command(["git", "switch", "-c", branch])


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug or "delivery")[:48]


def _pr_body(issue_number: int, target) -> str:
    return (
        "## Linked Issue\n\n"
        f"Closes #{issue_number}\n\n"
        "## Implementation Summary\n\n"
        f"- Delivery for Canonical Draft `{target.draft_id}` is in progress.\n\n"
        "## Acceptance Criteria Evidence\n\n"
        "- Pending implementation and required CI checks.\n\n"
        "## Changed Files / Scope\n\n"
        "- Pending implementation within the approved Draft scope.\n\n"
        "## Documentation Changes\n\n"
        "- Pending implementation.\n\n"
        "## Important Technical Decisions\n\n"
        f"- Delivery route: `{target.route}`.\n\n"
        "## Known Limitations\n\n"
        "- Draft PR; do not merge before human review.\n"
    )


def _number(url: str, kind: str) -> int:
    match = re.search(rf"/{kind}/(\d+)\s*$", url)
    if not match:
        raise ValueError(f"Could not determine {kind} number from: {url}")
    return int(match.group(1))


def _json_command(command: list[str]):
    return json.loads(_command(command))


def _command(command: list[str]) -> str:
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()
        raise ValueError(f"Command failed ({' '.join(command[:3])}): {detail}")
    return (completed.stdout or completed.stderr).strip()


def _add_repo_root_to_path() -> None:
    roots = [Path.cwd().resolve(), *Path.cwd().resolve().parents]
    for parent in [*roots, *Path(__file__).resolve().parents]:
        runtime = parent / ".simple_tool" / "runtime"
        if (runtime / "simple_flow_agent").is_dir():
            sys.path.insert(0, str(runtime))
            return
        if (parent / "simple_flow_agent").is_dir():
            sys.path.insert(0, str(parent))
            return


if __name__ == "__main__":
    raise SystemExit(main())
