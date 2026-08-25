from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlparse


@dataclass(frozen=True)
class DocumentationStartPlan:
    draft_id: str
    issue_title: str
    doc_path: str
    marker: str
    repo: str


def main(argv: list[str] | None = None) -> int:
    _add_repo_root_to_path()

    from simple_flow_agent.drafts import DraftStore

    parser = argparse.ArgumentParser(
        description="Start the Simple Flow DOCUMENTATION path from an append-only draft."
    )
    parser.add_argument("--draft-id", required=True)
    parser.add_argument("--drafts-dir", default=".simple_tool/drafts")
    parser.add_argument("--repo", required=True, help="GitHub owner/repo or repository URL.")
    parser.add_argument("--gh-path", default="gh")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args(argv)

    try:
        drafts_dir = Path(args.drafts_dir)
        draft = DraftStore(drafts_dir).read(args.draft_id)
        plan = build_plan(draft, normalize_repo(args.repo))
        if args.plan_only:
            print(json.dumps({"status": "planned", **asdict(plan)}, indent=2))
            return 0
        result = execute_plan(plan, drafts_dir=drafts_dir, gh_path=args.gh_path)
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps({"status": "ok", **result}, indent=2))
    return 0


def build_plan(draft, repo: str) -> DocumentationStartPlan:
    if draft.work_type != "DOCUMENTATION":
        raise ValueError(f"start_documentation only supports DOCUMENTATION drafts: {draft.work_type}")

    marker, doc_path = _parse_append_change(draft.fields["Change"])
    affected_docs = _list_field(draft.fields["Affected Project Documents"])
    if doc_path not in affected_docs:
        raise ValueError(
            f"Draft change targets {doc_path}, but affected documents are: {', '.join(affected_docs)}"
        )

    return DocumentationStartPlan(
        draft_id=draft.draft_id,
        issue_title=draft.fields["Change"],
        doc_path=doc_path,
        marker=marker,
        repo=repo,
    )


def execute_plan(
    plan: DocumentationStartPlan,
    *,
    drafts_dir: Path,
    gh_path: str,
) -> dict[str, str]:
    draft_body = drafts_dir / f"{plan.draft_id}.md"
    if not draft_body.exists():
        raise ValueError(f"Draft Markdown body not found: {draft_body}")

    issue_url = _run(
        [
            gh_path,
            "issue",
            "create",
            "--repo",
            plan.repo,
            "--title",
            plan.issue_title,
            "--body-file",
            str(draft_body),
        ]
    ).strip()
    issue_number = _issue_number(issue_url)
    branch = f"documentation/{issue_number}-phase4-smoke"

    _run(["git", "checkout", "-B", branch])
    _append_marker(Path(plan.doc_path), plan.marker)
    _run(["git", "add", plan.doc_path])
    _run(["git", "commit", "-m", f"docs: apply {plan.draft_id}"])
    _run(["git", "push", "--force-with-lease", "--set-upstream", "origin", branch])

    with tempfile.TemporaryDirectory(prefix="simple-flow-pr-") as tmpdir:
        body_path = Path(tmpdir) / "pr-body.md"
        body_path.write_text(_pr_body(issue_number, plan), encoding="utf-8")
        pr_url = _run(
            [
                gh_path,
                "pr",
                "create",
                "--repo",
                plan.repo,
                "--base",
                "main",
                "--head",
                branch,
                "--title",
                plan.issue_title,
                "--body-file",
                str(body_path),
                "--draft",
            ]
        ).strip()

    return {
        "draft_id": plan.draft_id,
        "issue_number": str(issue_number),
        "issue_url": issue_url,
        "branch": branch,
        "pr_url": pr_url,
        "stop_point": "HUMAN_PR_REVIEW",
    }


def normalize_repo(raw: str) -> str:
    value = raw.strip()
    if value.startswith("git@github.com:"):
        return value.removeprefix("git@github.com:").removesuffix(".git")
    parsed = urlparse(value)
    if parsed.netloc.lower() == "github.com":
        return parsed.path.strip("/").removesuffix(".git")
    return value.removesuffix(".git")


def _parse_append_change(change: str) -> tuple[str, str]:
    match = re.fullmatch(r"Append ['\"](.+)['\"] to ([^ ]+)", change.strip())
    if not match:
        raise ValueError("DOCUMENTATION helper requires Change like: Append 'text' to docs/file.md")
    return match.group(1), match.group(2)


def _list_field(raw: str) -> list[str]:
    items = []
    for line in raw.splitlines():
        value = line.strip()
        if not value:
            continue
        if value.startswith(("- ", "* ")):
            value = value[2:].strip()
        items.append(value)
    return items


def _append_marker(path: Path, marker: str) -> None:
    if not path.exists():
        raise ValueError(f"Approved documentation path does not exist: {path}")
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    separator = "" if text.endswith("\n") else "\n"
    path.write_text(f"{text}{separator}\n{marker}\n", encoding="utf-8")


def _pr_body(issue_number: int, plan: DocumentationStartPlan) -> str:
    return (
        "## Linked Issue\n\n"
        f"Closes #{issue_number}\n\n"
        "## Implementation Summary\n\n"
        f"- Applied approved DOCUMENTATION draft `{plan.draft_id}`.\n\n"
        "## Acceptance Criteria Evidence\n\n"
        "- Documentation-only smoke change applied.\n\n"
        "## Changed Files / Scope\n\n"
        f"- {plan.doc_path}\n\n"
        "## Documentation Changes\n\n"
        f"- {plan.doc_path}\n\n"
        "## Important Technical Decisions\n\n"
        "None\n\n"
        "## Known Limitations\n\n"
        "None\n"
    )


def _issue_number(issue_url: str) -> int:
    match = re.search(r"/issues/(\d+)\s*$", issue_url)
    if not match:
        raise ValueError(f"Could not determine issue number from gh output: {issue_url}")
    return int(match.group(1))


def _run(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=command_env(command),
        check=True,
    )
    return (completed.stdout or completed.stderr).strip()


def command_env(command: list[str]) -> dict[str, str]:
    env = os.environ.copy()
    executable = command[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
    if executable in {"gh", "gh.exe"}:
        for key in list(env):
            if key.lower().endswith("_proxy"):
                env.pop(key, None)
    return env


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
    return


if __name__ == "__main__":
    raise SystemExit(main())
