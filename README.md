# AgentArena Local

AgentArena Local is a local evaluation platform for comparing AI coding agents in your own Git repositories.

## v0.3

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
- Planning Evaluation with `plan.md` output and keyword scoring
- Feature Slice Generation checks
- AGENTS.md A/B tests
- manual adapters for Cursor, Cline, and Windsurf
- task-type and overall leaderboards
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

## Planning Evaluation

Planning tasks should produce a plan without changing code. AgentArena saves the
agent output as `plan.md`, scores expected keyword coverage, and records
`planning_modified_code` if the worktree has a diff.

```powershell
agentarena run --agents claude,codex --task examples/planning_student_filter/task.yaml
agentarena leaderboard --type planning
```

## Feature Slice Generation

Generation tasks are small changes inside an existing project. Use
`expected_files_may_change` as soft scope guidance and `feature_checks` for
required or forbidden diff patterns.

```powershell
agentarena run --agents claude,codex --task examples/python_feature_todo_filter/task.yaml
agentarena leaderboard --type generation
```

## AGENTS.md A/B Test

Variants live in subdirectories that each contain an `AGENTS.md` file.

```powershell
agentarena abtest --agents claude,codex --task examples/agents_md_abtest/task.yaml --variants examples/agents_md_abtest/variants
agentarena leaderboard --type abtest
```

## Manual IDE Agents

`cursor`, `cline`, and `windsurf` use manual mode. AgentArena prints the isolated
worktree path and task instruction, then waits for you to open that directory in
the chosen tool and press Enter when finished.

```powershell
agentarena run --agent cursor --task examples/python_feature_todo_filter/task.yaml --keep-worktree
agentarena run --agent cline --task examples/python_feature_todo_filter/task.yaml --keep-worktree
agentarena run --agent windsurf --task examples/python_feature_todo_filter/task.yaml --keep-worktree
```

## Leaderboards And Dashboard

```powershell
agentarena leaderboard --type debug
agentarena leaderboard --type generation
agentarena leaderboard --type planning
agentarena leaderboard --overall
agentarena dashboard
```

The dashboard includes score, diff, files changed, duration, violations, task type
score comparison, AGENTS.md variant comparison, pass rate by agent, and failure
reason distribution.
