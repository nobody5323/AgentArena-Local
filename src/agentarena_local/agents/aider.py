from agentarena_local.agents.base import CliAgentAdapter


class AiderAgentAdapter(CliAgentAdapter):
    name = "aider"
    executable = "aider"

    def build_command(self, instruction: str) -> list[str]:
        return [self.executable, "--message", instruction]
