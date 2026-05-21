from __future__ import annotations

import time
from pathlib import Path

from agentarena_local.agents.base import AgentExecutionResult, BaseAgentAdapter


class ManualAgentAdapter(BaseAgentAdapter):
    name = "manual"

    def is_available(self) -> bool:
        return True

    def run(
        self,
        instruction: str,
        cwd: Path,
        timeout: int | None = None,
    ) -> AgentExecutionResult:
        started = time.monotonic()
        print(f"Manual AgentArena worktree: {cwd}")
        print("Instruction:")
        print(instruction)
        input("Press Enter when the manual agent run is complete...")
        return AgentExecutionResult(
            agent_name=self.name,
            command=None,
            exit_code=0,
            stdout="Manual run completed by user.\n",
            stderr="",
            duration_seconds=time.monotonic() - started,
        )
