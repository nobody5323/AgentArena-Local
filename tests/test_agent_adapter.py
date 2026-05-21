from __future__ import annotations

import sys
from pathlib import Path

from agentarena_local.agents.base import CliAgentAdapter


class PythonSleepAdapter(CliAgentAdapter):
    name = "python-sleep"
    executable = sys.executable

    def build_command(self, instruction: str) -> list[str]:
        return [self.resolved_executable() or self.executable, "-c", instruction]


def test_cli_agent_timeout_kills_process_tree(tmp_path: Path) -> None:
    result = PythonSleepAdapter().run("import time; time.sleep(30)", tmp_path, timeout=1)

    assert result.exit_code == 124
    assert result.timed_out is True
    assert result.duration_seconds < 10
