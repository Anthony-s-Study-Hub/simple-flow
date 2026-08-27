from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys


def main(argv: list[str] | None = None) -> int:
    _add_repo_root_to_path()

    from simple_flow_agent.review_triage import classify_review_finding

    parser = argparse.ArgumentParser(
        description="Classify a Simple Flow human PR review finding."
    )
    parser.add_argument("--relationship", required=True, choices=["CURRENT", "SUBISSUE", "NEW ISSUE"])
    parser.add_argument("--merge-impact", required=True, choices=["BLOCKING", "FOLLOW-UP"])
    parser.add_argument("--source-issue", type=int)
    parser.add_argument("--source-pr", type=int)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--decision-id")
    parser.add_argument("--target-draft-id")
    parser.add_argument("--stage", choices=["DRAFT", "DELIVERY"], default="DELIVERY")
    parser.add_argument(
        "--resolution",
        choices=[
            "SUPERSEDE_DRAFT",
            "CREATE_CHILD_DRAFT",
            "CREATE_INDEPENDENT_DRAFT",
            "PATCH_CURRENT_PR",
            "CREATE_LINKED_FOLLOW_UP",
            "CREATE_INDEPENDENT_FOLLOW_UP",
        ],
    )
    parser.add_argument("--output", help="Write the durable decision JSON to this path.")
    args = parser.parse_args(argv)

    try:
        result = classify_review_finding(
            relationship=args.relationship,
            merge_impact=args.merge_impact,
            source_issue=args.source_issue,
            source_pr=args.source_pr,
            reason=args.reason,
            decision_id=args.decision_id,
            target_draft_id=args.target_draft_id,
            stage=args.stage,
            resolution=args.resolution,
        )
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    output = {"status": "ok", **asdict(result)}
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0


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
