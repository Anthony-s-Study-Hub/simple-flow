from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess

from simple_flow_test_harness.models import CommandResult


def run_command(
    command: list[str] | tuple[str, ...],
    *,
    cwd: str | Path,
    timeout_seconds: int = 120,
    check: bool = False,
) -> CommandResult:
    process = subprocess.Popen(
        list(command),
        cwd=Path(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_creation_flags(),
        start_new_session=os.name != "nt",
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        _terminate_process_tree(process)
        stdout, stderr = process.communicate()
        raise subprocess.TimeoutExpired(
            list(command),
            timeout_seconds,
            output=stdout,
            stderr=stderr,
        ) from exc

    result = CommandResult(
        command=tuple(str(part) for part in command),
        cwd=str(Path(cwd)),
        exit_code=process.returncode,
        stdout=stdout,
        stderr=stderr,
    )
    if check and result.exit_code != 0:
        raise CommandFailure(result)
    return result


def _creation_flags() -> int:
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return

    if os.name == "nt":
        _taskkill(process.pid)
        return

    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return


def _taskkill(pid: int) -> None:
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return


class CommandFailure(RuntimeError):
    def __init__(self, result: CommandResult):
        super().__init__(
            f"Command failed with exit {result.exit_code}: {' '.join(result.command)}\n"
            f"{result.stderr or result.stdout}"
        )
        self.result = result
