from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from simple_flow_test_harness.commands import run_command


def test_run_command_timeout_terminates_child_process_tree(tmp_path: Path) -> None:
    marker = tmp_path / "child.pid"
    child_script = tmp_path / "child_sleep.py"
    parent_script = tmp_path / "parent_sleep.py"

    child_script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import os",
                "import sys",
                "import time",
                "Path(sys.argv[1]).write_text(str(os.getpid()), encoding='utf-8')",
                "time.sleep(30)",
            ]
        ),
        encoding="utf-8",
    )
    parent_script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import subprocess",
                "import sys",
                "import time",
                "marker = Path(sys.argv[2])",
                "subprocess.Popen([sys.executable, sys.argv[1], str(marker)])",
                "deadline = time.monotonic() + 10",
                "while not marker.exists() and time.monotonic() < deadline:",
                "    time.sleep(0.05)",
                "time.sleep(30)",
            ]
        ),
        encoding="utf-8",
    )

    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        run_command(
            [sys.executable, str(parent_script), str(child_script), str(marker)],
            cwd=tmp_path,
            timeout_seconds=1,
        )
    elapsed = time.monotonic() - started

    child_pid = int(marker.read_text(encoding="utf-8"))
    time.sleep(0.5)
    child_still_alive = _pid_is_running(child_pid)
    _kill_pid(child_pid)

    assert elapsed < 5
    assert not child_still_alive


def _pid_is_running(pid: int) -> bool:
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        return str(pid) in result.stdout
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _kill_pid(pid: int) -> None:
    if not _pid_is_running(pid):
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            text=True,
            timeout=10,
        )
    else:
        os.kill(pid, signal.SIGKILL)
