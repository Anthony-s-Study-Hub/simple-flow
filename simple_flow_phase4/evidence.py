from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from simple_flow_phase4.commands import run_command
from simple_flow_phase4.models import CommandResult, Phase4Config


def collect_state(
    *,
    project_path: Path,
    repo_full_name: str,
    config: Phase4Config,
    codex_result: CommandResult | None = None,
) -> dict[str, Any]:
    commands: dict[str, Any] = {}

    def capture(key: str, command: list[str], timeout_seconds: int = 60) -> CommandResult:
        result = run_command(command, cwd=project_path, timeout_seconds=timeout_seconds)
        commands[key] = result.to_json_data()
        return result

    status = capture("git_status", ["git", "status", "--short", "--branch"])
    branches = capture("git_branches", ["git", "branch", "--format=%(refname:short)"])
    log = capture("git_log", ["git", "log", "--oneline", "--decorate", "-20"])
    changed_files = capture("git_changed_files", ["git", "diff", "--name-only", "main...HEAD"])

    issues = _load_json_command(
        capture(
            "github_issues",
            [
                config.gh_path,
                "issue",
                "list",
                "--repo",
                repo_full_name,
                "--state",
                "all",
                "--json",
                "number,state,title,body,url,closed",
                "--limit",
                "100",
            ],
        )
    )
    prs = _load_json_command(
        capture(
            "github_prs",
            [
                config.gh_path,
                "pr",
                "list",
                "--repo",
                repo_full_name,
                "--state",
                "all",
                "--json",
                "number,state,title,body,url,isDraft,headRefName,baseRefName,mergedAt,statusCheckRollup,reviewDecision",
                "--limit",
                "100",
            ],
        )
    )

    draft_data, draft_text = _read_drafts(project_path)
    tdd_evidence = sorted(str(path.relative_to(project_path)) for path in (project_path / ".simple-flow" / "tdd-evidence").glob("*.json"))
    local_branches = [branch.strip() for branch in branches.stdout.splitlines() if branch.strip()]
    development_branches = [
        branch
        for branch in local_branches
        if branch not in {"main", "master"} and not branch.startswith("remotes/")
    ]

    open_issues = [item for item in issues if item.get("state") == "OPEN"]
    closed_issues = [item for item in issues if item.get("state") == "CLOSED"]
    open_prs = [item for item in prs if item.get("state") == "OPEN"]
    merged_prs = [item for item in prs if item.get("state") == "MERGED" or item.get("mergedAt")]
    draft_prs = [item for item in prs if item.get("isDraft")]

    codex_stdout = codex_result.stdout if codex_result else ""
    codex_stderr = codex_result.stderr if codex_result else ""
    codex_output = f"{codex_stdout}\n{codex_stderr}".strip()

    metrics = {
        "git_status_clean": status.exit_code == 0 and not _dirty_status(status.stdout),
        "local_development_branch_count": len(development_branches),
        "changed_file_count": len([line for line in changed_files.stdout.splitlines() if line.strip()]),
        "draft_count": len(draft_data),
        "feature_draft_count": _count_drafts(draft_data, "FEATURE"),
        "documentation_draft_count": _count_drafts(draft_data, "DOCUMENTATION"),
        "draft_text": draft_text,
        "tdd_evidence_count": len(tdd_evidence),
        "open_issue_count": len(open_issues),
        "closed_issue_count": len(closed_issues),
        "total_issue_count": len(issues),
        "open_pr_count": len(open_prs),
        "merged_pr_count": len(merged_prs),
        "draft_pr_count": len(draft_prs),
        "total_pr_count": len(prs),
        "codex_exit_code": codex_result.exit_code if codex_result else None,
        "codex_output": codex_output,
        "codex_blocked_or_stopped": _looks_blocked_or_stopped(codex_output, codex_result.exit_code if codex_result else 0),
    }

    return {
        "commands": commands,
        "metrics": metrics,
        "git": {
            "status": status.stdout,
            "branches": local_branches,
            "development_branches": development_branches,
            "log": log.stdout,
            "changed_files": [line for line in changed_files.stdout.splitlines() if line.strip()],
        },
        "github": {
            "issues": issues,
            "pull_requests": prs,
            "open_issues": open_issues,
            "closed_issues": closed_issues,
            "open_pull_requests": open_prs,
            "merged_pull_requests": merged_prs,
        },
        "drafts": draft_data,
        "tdd_evidence": tdd_evidence,
        "codex": codex_result.to_json_data() if codex_result else None,
    }


def _load_json_command(result: CommandResult) -> list[dict[str, Any]]:
    if result.exit_code != 0 or not result.stdout.strip():
        return []
    data = json.loads(result.stdout)
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _read_drafts(project_path: Path) -> tuple[list[dict[str, Any]], str]:
    draft_data: list[dict[str, Any]] = []
    text_parts: list[str] = []
    for path in sorted((project_path / ".simple-flow").glob("**/*")):
        if path.is_file() and path.suffix == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and "draft_id" in data and "work_type" in data:
                draft_data.append(data)
                text_parts.append(json.dumps(data, sort_keys=True))
        elif path.is_file() and path.suffix == ".md" and "draft" in path.name.lower():
            text_parts.append(path.read_text(encoding="utf-8"))
    return draft_data, "\n".join(text_parts)


def _count_drafts(drafts: list[dict[str, Any]], work_type: str) -> int:
    return sum(1 for draft in drafts if draft.get("work_type") == work_type)


def _dirty_status(status: str) -> bool:
    for line in status.splitlines():
        if line.startswith("##"):
            continue
        if line.strip():
            return True
    return False


def _looks_blocked_or_stopped(output: str, exit_code: int) -> bool:
    lowered = output.lower()
    markers = ("blocked", "stop", "cannot", "must not", "gate fail", "failed", "error")
    return exit_code != 0 or any(marker in lowered for marker in markers)
