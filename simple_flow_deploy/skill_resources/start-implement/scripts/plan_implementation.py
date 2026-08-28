from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main(argv: list[str] | None = None) -> int:
    _add_repo_root_to_path()

    from simple_flow_agent.drafts import DraftStore
    from simple_flow_agent.implementation_plan import ImplementationIntent, plan_implementation

    parser = argparse.ArgumentParser(
        description="Select and validate one deterministic Simple Flow implementation plan."
    )
    parser.add_argument("--draft-id")
    parser.add_argument("--intent", help="JSON object with tags, components, and optional terms.")
    parser.add_argument("--output", help="Optional durable file for the ready plan JSON.")
    parser.add_argument("--status-file", default=".simple_tool/status.json")
    parser.add_argument("--drafts-dir", default=".simple_tool/drafts")
    args = parser.parse_args(argv)

    try:
        intent = _intent(args.intent, ImplementationIntent)
        active_draft_id = _active_draft_id(args.status_file)
        plan = plan_implementation(
            DraftStore(args.drafts_dir),
            draft_id=args.draft_id,
            active_draft_id=active_draft_id,
            intent=intent,
        )
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    output = {"status": "ready", **plan.to_json_data()}
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0


def _intent(path: str | None, intent_type):
    if not path:
        return None
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Intent JSON must be an object.")
    return intent_type.from_data(raw)


def _active_draft_id(path: str) -> str | None:
    status_path = Path(path)
    if not status_path.exists():
        return None
    raw = json.loads(status_path.read_text(encoding="utf-8"))
    active = raw.get("active_draft")
    return str(active) if active else None


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
