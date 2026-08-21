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
    parser.add_argument("--source-issue", required=True, type=int)
    parser.add_argument("--source-pr", required=True, type=int)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args(argv)

    try:
        result = classify_review_finding(
            relationship=args.relationship,
            merge_impact=args.merge_impact,
            source_issue=args.source_issue,
            source_pr=args.source_pr,
            reason=args.reason,
        )
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    output = {"status": "ok", **asdict(result)}
    print(json.dumps(output, indent=2))
    return 0


def _add_repo_root_to_path() -> None:
    for parent in Path(__file__).resolve().parents:
        if (parent / "simple_flow_agent").is_dir():
            sys.path.insert(0, str(parent))
            return
    return


if __name__ == "__main__":
    raise SystemExit(main())
