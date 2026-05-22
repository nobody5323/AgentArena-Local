from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


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

    def resolved_executable(self) -> str | None:
        if sys.platform == "win32":
            for suffix in (".cmd", ".exe", ".bat", ""):
                resolved = shutil.which(f"{self.executable}{suffix}")
                if resolved:
                    return resolved
        return shutil.which(self.executable)

    def is_available(self) -> bool:
        return self.resolved_executable() is not None

    def build_command(self, instruction: str) -> list[str]:
        return [self.resolved_executable() or self.executable, instruction]

    def _kill_process_tree(self, process: subprocess.Popen[str]) -> None:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            if process.poll() is None:
                process.kill()
            return
        os.killpg(process.pid, signal.SIGKILL)

    def _run_process(
        self,
        command: list[str],
        cwd: Path,
        timeout: int | None,
        on_process: Callable[[subprocess.Popen[str]], None] | None,
    ) -> AgentExecutionResult:
        started = time.monotonic()
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            start_new_session=sys.platform != "win32",
        )
        if on_process is not None:
            on_process(process)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._kill_process_tree(process)
            try:
                stdout, stderr = process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                stdout, stderr = "", ""
            return AgentExecutionResult(
                agent_name=self.name,
                command=command,
                exit_code=124,
                stdout=stdout or "",
                stderr=stderr or "",
                duration_seconds=time.monotonic() - started,
                timed_out=True,
            )
        return AgentExecutionResult(
            agent_name=self.name,
            command=command,
            exit_code=process.returncode,
            stdout=stdout or "",
            stderr=stderr or "",
            duration_seconds=time.monotonic() - started,
        )

    def run(
        self,
        instruction: str,
        cwd: Path,
        timeout: int | None = None,
    ) -> AgentExecutionResult:
        return self.run_with_callback(instruction, cwd, timeout=timeout)

    def run_with_callback(
        self,
        instruction: str,
        cwd: Path,
        timeout: int | None = None,
        on_process: Callable[[subprocess.Popen[str]], None] | None = None,
    ) -> AgentExecutionResult:
        command = self.build_command(instruction)
        try:
            return self._run_process(command, cwd, timeout, on_process)
        except OSError as exc:
            return AgentExecutionResult(
                agent_name=self.name,
                command=command,
                exit_code=126,
                stdout="",
                stderr=f"Failed to start {self.name}: {exc}\n",
                duration_seconds=0.0,
            )
