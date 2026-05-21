# AgentArena Local

AgentArena Local is a local evaluation platform for comparing AI coding agents in your own Git repositories.

## v0.1

The first version includes:

- Typer CLI
- `agentarena init`
- `agentarena validate <task.yaml>`
- Pydantic task schema
- task types: `planning`, `debug`, `generation`
- example task
- pytest tests

## Quick Start

```powershell
pip install -e ".[dev]"
agentarena init
agentarena validate examples/python_debug_login/task.yaml
pytest
```
