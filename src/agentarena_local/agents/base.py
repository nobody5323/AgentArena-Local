from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentExecutionResult:
    agent_name: str
    command: list[str] | None
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


class BaseAgentAdapter:
    name: str = "base"

    def is_available(self) -> bool:
        raise NotImplementedError

    def run(
        self,
        instruction: str,
        cwd: Path,
        timeout: int | None = None,
    ) -> AgentExecutionResult:
        raise NotImplementedError


class CliAgentAdapter(BaseAgentAdapter):
    executable: str

    def is_available(self) -> bool:
        return shutil.which(self.executable) is not None

    def build_command(self, instruction: str) -> list[str]:
        return [self.executable, instruction]

    def run(
        self,
        instruction: str,
        cwd: Path,
        timeout: int | None = None,
    ) -> AgentExecutionResult:
        command = self.build_command(instruction)
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return AgentExecutionResult(
                agent_name=self.name,
                command=command,
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                duration_seconds=time.monotonic() - started,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            return AgentExecutionResult(
                agent_name=self.name,
                command=command,
                exit_code=124,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=time.monotonic() - started,
                timed_out=True,
            )
