from __future__ import annotations

import time
from pathlib import Path

from agentarena_local.agents.base import AgentExecutionResult, BaseAgentAdapter


class ManualAgentAdapter(BaseAgentAdapter):
    name = "manual"
    tool_hint = "your preferred editor or agent"

    def is_available(self) -> bool:
        return True

    def run(
        self,
        instruction: str,
        cwd: Path,
        timeout: int | None = None,
    ) -> AgentExecutionResult:
        started = time.monotonic()
        print("=" * 72)
        print(f"AgentArena manual mode: {self.name}")
        print(f"Worktree path: {cwd}")
        print(f"Open this directory with {self.tool_hint}, complete the task, then return here.")
        print("-" * 72)
        print("Task instruction:")
        print(instruction)
        print("=" * 72)
        input("Press Enter when the manual agent run is complete...")
        return AgentExecutionResult(
            agent_name=self.name,
            command=None,
            exit_code=0,
            stdout=f"Manual run completed by user for {self.name}.\n",
            stderr="",
            duration_seconds=time.monotonic() - started,
        )
