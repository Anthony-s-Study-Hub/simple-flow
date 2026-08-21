from __future__ import annotations

import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_harness_package_uses_descriptive_module_name() -> None:
    assert not (ROOT / "simple_flow_phase4").exists()
    assert (ROOT / "simple_flow_test_harness").is_dir()

    cli = importlib.import_module("simple_flow_test_harness.cli")

    assert callable(cli.main)


def test_generated_root_tmp_dotfolders_are_ignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert ".tmp-*/" in gitignore
