# AgentArena Local

AgentArena Local is a local evaluation platform for comparing AI coding agents in your own Git repositories.

## v0.2

The current version includes:

- Typer CLI
- `agentarena init`
- `agentarena validate <task.yaml>`
- `agentarena run`
- `agentarena leaderboard`
- `agentarena report --format html`
- `agentarena dashboard`
- Pydantic task schema
- task types: `planning`, `debug`, `generation`
- agent adapters for `manual`, `claude`, `codex`, `gemini`, and `aider`
- Git worktree isolation
- diff, constraints, scoring, failure analysis, and saved JSON results
- example task
- pytest tests

## Quick Start

```powershell
pip install -e ".[dev]"
agentarena init
agentarena validate examples/python_debug_login/task.yaml
agentarena run --agents claude,codex,manual --task examples/python_debug_login/task.yaml
agentarena leaderboard
agentarena report --format html
agentarena dashboard
pytest
```

Run results are saved under `.agentarena/runs/<run_id>_<task_id>/<agent_name>/`.
Reports are saved under `.agentarena/reports/`.
