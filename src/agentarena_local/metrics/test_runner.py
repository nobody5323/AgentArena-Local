from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from agentarena_local.tasks import CommandSpec


@dataclass(frozen=True)
class CommandResult:
    name: str
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


@dataclass(frozen=True)
class CommandGroupResult:
    commands: list[CommandResult] = field(default_factory=list)
    passed: bool | None = None

    @property
    def stdout(self) -> str:
        return "\n".join(result.stdout for result in self.commands if result.stdout)

    @property
    def stderr(self) -> str:
        return "\n".join(result.stderr for result in self.commands if result.stderr)


def run_command(command: CommandSpec, cwd: Path) -> CommandResult:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command.command,
            cwd=cwd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=command.timeout_seconds,
            check=False,
        )
        return CommandResult(
            name=command.name,
            command=command.command,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_seconds=time.monotonic() - started,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return CommandResult(
            name=command.name,
            command=command.command,
            exit_code=124,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=time.monotonic() - started,
            timed_out=True,
        )


def run_commands(commands: list[CommandSpec], cwd: Path) -> CommandGroupResult:
    if not commands:
        return CommandGroupResult(commands=[], passed=None)

    results: list[CommandResult] = []
    for command in commands:
        result = run_command(command, cwd)
        results.append(result)
        if not result.succeeded:
            return CommandGroupResult(commands=results, passed=False)

    return CommandGroupResult(commands=results, passed=True)
