# AgentArena Local

AgentArena Local is a local benchmark platform for comparing AI coding agents in
your own Git repositories. It runs each agent in an isolated Git worktree,
collects diffs, runs tests, checks constraints, scores results, and generates
leaderboards plus static reports.

## Features

- Multi-agent adapters: Claude, Codex, Gemini, Aider, Manual, Cursor, Cline, Windsurf
- Debug, Planning, and Feature Slice Generation evaluations
- Git worktree isolation for every agent run
- `task.yaml` validation with Pydantic
- setup/test command execution with logs
- diff metrics, constraints, scoring, and failure analysis
- AGENTS.md A/B testing
- Rich CLI leaderboards and historical run browser
- Static HTML report and Plotly.js dashboard
- Bright anime-style Web GUI built with React, Vite, Tailwind, and Lightswind UI
- PyInstaller scripts for Windows EXE builds

## Installation

```powershell
pip install -e ".[dev]"
```

Python 3.11+ is recommended. Web GUI usage requires Node.js 18+.

## Quick Start

```powershell
agentarena init
agentarena validate examples/python_debug_login/task.yaml
agentarena run --agents claude,codex,manual --task examples/python_debug_login/task.yaml
agentarena leaderboard
agentarena report --format html
agentarena dashboard
```

Results are saved under `.agentarena/runs/`. Reports are saved under
`.agentarena/reports/`.

## Claude vs Codex

```powershell
agentarena run --agents claude,codex --task examples/python_debug_login/task.yaml
agentarena leaderboard --type debug
```

## Cursor / Cline / Windsurf Manual Mode

These adapters print the isolated worktree path and wait for you to open that
directory in the chosen tool. Press Enter in the terminal when the manual run is
finished.

```powershell
agentarena run --agent cursor --task examples/python_feature_todo_filter/task.yaml --keep-worktree
agentarena run --agent cline --task examples/python_feature_todo_filter/task.yaml --keep-worktree
agentarena run --agent windsurf --task examples/python_feature_todo_filter/task.yaml --keep-worktree
```

## Planning Evaluation

Planning tasks should not modify code. AgentArena stores agent output as
`plan.md`, scores expected keyword coverage, and records `planning_modified_code`
if a diff appears.

```powershell
agentarena run --agents claude,codex --task examples/planning_student_filter/task.yaml
agentarena leaderboard --type planning
```

## Debug Evaluation

Debug tasks focus on fixing an existing bug with tests and constraints.

```powershell
agentarena run --agents claude,codex,manual --task examples/python_debug_login/task.yaml
```

## Feature Slice Generation

Generation tasks implement a small feature inside an existing project. Use
`expected_files_may_change` and `feature_checks` in `task.yaml` to evaluate
feature completeness.

```powershell
agentarena run --agents claude,codex --task examples/python_feature_todo_filter/task.yaml
agentarena leaderboard --type generation
```

## AGENTS.md A/B Test

```powershell
agentarena abtest --agents claude,codex --task examples/agents_md_abtest/task.yaml --variants examples/agents_md_abtest/variants
agentarena leaderboard --type abtest
```

Variant directories must contain an `AGENTS.md` file:

```text
variants/
  no_agents/AGENTS.md
  simple/AGENTS.md
  strict/AGENTS.md
```

## Leaderboard

```powershell
agentarena leaderboard
agentarena leaderboard --type debug
agentarena leaderboard --type generation
agentarena leaderboard --type planning
agentarena leaderboard --type abtest
agentarena leaderboard --overall
```

## Dashboard

```powershell
agentarena dashboard
```

The dashboard includes total score, task type comparison, pass rate by agent,
failure reason distribution, AGENTS.md variant comparison, and diff-vs-score
scatter plots.

## Web GUI Usage

```powershell
agentarena gui
```

Open `http://127.0.0.1:5173`. The command starts the FastAPI backend on
`http://127.0.0.1:8765` and the Vite Web GUI on port `5173`. In v0.5 the GUI
uses Chinese interface text, can start non-interactive agent runs, launch Cursor
GUI worktrees, refresh the live leaderboard, and generate reports or dashboards.

## Historical Runs

```powershell
agentarena runs
agentarena runs --latest
agentarena show <run_id>
```

## Build EXE

```powershell
python scripts/build_exe.py
```

Expected outputs:

- `dist/AgentArena.exe`

## Release Check

```powershell
python scripts/release.py
```

The release script runs pytest, checks README/examples/pyproject, attempts to
build a wheel, and prints a checklist.

## Roadmap

- More agent adapters
- Stronger task schemas and scoring presets
- Optional sandbox backends
- Richer report comparison views
- Import/export benchmark bundles
