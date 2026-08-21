from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simple_flow_deploy.installer import install


def main() -> int:
    parser = argparse.ArgumentParser(description="Install Simple Flow into a target project.")
    parser.add_argument("--target", required=True)
    parser.add_argument("--project-name", default="new-project")
    parser.add_argument("--test-command", default="python -m pytest")
    parser.add_argument("--scope", action="append", default=[])
    parser.add_argument("--documentation", action="append", default=[])
    parser.add_argument("--clean-target", action="store_true")
    args = parser.parse_args()

    report = install(
        source_root=ROOT,
        target=args.target,
        project_name=args.project_name,
        test_command=args.test_command,
        scope=args.scope or ["src/"],
        documentation=args.documentation or ["docs/"],
        clean_target=args.clean_target,
    )
    print(report.to_json())
    return 0 if report.status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())

