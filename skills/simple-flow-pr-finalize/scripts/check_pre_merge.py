from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Any


def main(argv: list[str] | None = None) -> int:
    _add_repo_root_to_path()

    from simple_flow_agent.finalize import PRState, pre_merge_check

    parser = argparse.ArgumentParser(
        description="Run deterministic Simple Flow PR-Finalize pre-merge checks."
    )
    parser.add_argument("--state", required=True, help="JSON file containing objective PR state.")
    parser.add_argument(
        "--authorized",
        action="store_true",
        help="Set only when the human explicitly invoked PR-Finalize for this PR.",
    )
    args = parser.parse_args(argv)

    try:
        data = json.loads(Path(args.state).read_text(encoding="utf-8"))
        state = PRState(
            exists=bool(data["exists"]),
            open=bool(data["open"]),
            draft=bool(data["draft"]),
            required_checks={str(k): bool(v) for k, v in dict(data["required_checks"]).items()},
            unresolved_conversations=int(data["unresolved_conversations"]),
            commits_after_human_review=int(data["commits_after_human_review"]),
            linked_issue_closed=bool(data["linked_issue_closed"]),
            head_branch_deleted=bool(data["head_branch_deleted"]),
            project_item_updated=bool(data["project_item_updated"]),
        )
        result = pre_merge_check(state, authorized=args.authorized)
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps({"status": "ok", **asdict(result)}, indent=2))
    return 0


def _add_repo_root_to_path() -> None:
    for parent in Path(__file__).resolve().parents:
        if (parent / "simple_flow_agent").is_dir():
            sys.path.insert(0, str(parent))
            return
    raise RuntimeError("Could not find repository root containing simple_flow_agent.")


if __name__ == "__main__":
    raise SystemExit(main())
