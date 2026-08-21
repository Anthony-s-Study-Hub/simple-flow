from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Any


def main(argv: list[str] | None = None) -> int:
    _add_repo_root_to_path()

    from simple_flow_agent.drafts import DraftStore
    from simple_flow_agent.start_implement import select_start_path

    parser = argparse.ArgumentParser(
        description="Select the deterministic Simple Flow Start-Implement path."
    )
    parser.add_argument("--draft-id", required=True)
    parser.add_argument("--drafts-dir", default=".simple-flow/drafts")
    parser.add_argument(
        "--triage-file",
        action="append",
        default=[],
        help="JSON output from Review-Triage. May be repeated.",
    )
    args = parser.parse_args(argv)

    try:
        store = DraftStore(args.drafts_dir)
        triage_results = _load_triage_results(args.triage_file)
        plan = select_start_path(store, args.draft_id, triage_results)
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps({"status": "ok", **asdict(plan)}, indent=2))
    return 0


def _add_repo_root_to_path() -> None:
    for parent in Path(__file__).resolve().parents:
        if (parent / "simple_flow_agent").is_dir():
            sys.path.insert(0, str(parent))
            return
    raise RuntimeError("Could not find repository root containing simple_flow_agent.")


def _load_triage_results(paths: list[str]):
    from simple_flow_agent.review_triage import classify_review_finding

    results = []
    for path in paths:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        for item in _items(raw):
            results.append(
                classify_review_finding(
                    relationship=str(item["relationship"]),
                    merge_impact=str(item["merge_impact"]),
                    source_issue=int(item["source_issue"]),
                    source_pr=int(item["source_pr"]),
                    reason=str(item["reason"]),
                )
            )
    return results


def _items(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [dict(item) for item in raw]
    if isinstance(raw, dict) and isinstance(raw.get("results"), list):
        return [dict(item) for item in raw["results"]]
    if isinstance(raw, dict):
        return [raw]
    raise ValueError("Triage JSON must be an object, an object with results, or a list.")


if __name__ == "__main__":
    raise SystemExit(main())
