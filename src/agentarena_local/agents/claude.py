from agentarena_local.agents.base import CliAgentAdapter


class ClaudeAgentAdapter(CliAgentAdapter):
    name = "claude"
    executable = "claude"

    def build_command(self, instruction: str) -> list[str]:
        return [
            self.resolved_executable() or self.executable,
            "-p",
            "--permission-mode",
            "bypassPermissions",
            instruction,
        ]
