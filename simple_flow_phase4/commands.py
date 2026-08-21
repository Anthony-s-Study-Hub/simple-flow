from __future__ import annotations

from pathlib import Path
import subprocess

from simple_flow_phase4.models import CommandResult


def run_command(
    command: list[str] | tuple[str, ...],
    *,
    cwd: str | Path,
    timeout_seconds: int = 120,
    check: bool = False,
) -> CommandResult:
    completed = subprocess.run(
        list(command),
        cwd=Path(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
    )
    result = CommandResult(
        command=tuple(str(part) for part in command),
        cwd=str(Path(cwd)),
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    if check and result.exit_code != 0:
        raise CommandFailure(result)
    return result


class CommandFailure(RuntimeError):
    def __init__(self, result: CommandResult):
        super().__init__(
            f"Command failed with exit {result.exit_code}: {' '.join(result.command)}\n"
            f"{result.stderr or result.stdout}"
        )
        self.result = result
