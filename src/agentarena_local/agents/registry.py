from __future__ import annotations

from agentarena_local.agents.aider import AiderAgentAdapter
from agentarena_local.agents.base import BaseAgentAdapter
from agentarena_local.agents.claude import ClaudeAgentAdapter
from agentarena_local.agents.cline import ClineAgentAdapter
from agentarena_local.agents.codex import CodexAgentAdapter
from agentarena_local.agents.cursor import CursorAgentAdapter
from agentarena_local.agents.gemini import GeminiAgentAdapter
from agentarena_local.agents.manual import ManualAgentAdapter
from agentarena_local.agents.windsurf import WindsurfAgentAdapter


_AGENTS: dict[str, type[BaseAgentAdapter]] = {
    "manual": ManualAgentAdapter,
    "claude": ClaudeAgentAdapter,
    "codex": CodexAgentAdapter,
    "gemini": GeminiAgentAdapter,
    "aider": AiderAgentAdapter,
    "cursor": CursorAgentAdapter,
    "cline": ClineAgentAdapter,
    "windsurf": WindsurfAgentAdapter,
}


def get_agent(name: str) -> BaseAgentAdapter:
    try:
        return _AGENTS[name]()
    except KeyError as exc:
        known = ", ".join(sorted(_AGENTS))
        raise ValueError(f"Unknown agent {name!r}. Known agents: {known}") from exc


def list_agents() -> list[str]:
    return sorted(_AGENTS)
