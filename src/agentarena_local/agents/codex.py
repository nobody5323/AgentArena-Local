from agentarena_local.agents.base import CliAgentAdapter


class CodexAgentAdapter(CliAgentAdapter):
    name = "codex"
    executable = "codex"

    def build_command(self, instruction: str) -> list[str]:
        return [
            self.resolved_executable() or self.executable,
            "exec",
            "--sandbox",
            "workspace-write",
            "--skip-git-repo-check",
            instruction,
        ]
