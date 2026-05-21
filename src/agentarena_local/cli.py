from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Annotated

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from agentarena_local.agents.base import AgentExecutionResult
from agentarena_local.agents.registry import get_agent
from agentarena_local.config import init_workspace
from agentarena_local.gitops.diff import DiffStats, collect_diff
from agentarena_local.gitops.worktree import create_worktree, ensure_git_repo, remove_worktree
from agentarena_local.metrics.constraints import check_constraints
from agentarena_local.metrics.failure_analysis import analyze_failures
from agentarena_local.metrics.scorer import calculate_score
from agentarena_local.metrics.test_runner import CommandGroupResult, run_commands
from agentarena_local.tasks import TaskConfig, load_task

app = typer.Typer(
    name="agentarena",
    help="AgentArena Local: evaluate AI coding agents in local Git repositories.",
    no_args_is_help=True,
)
console = Console()


def _format_validation_error(exc: ValidationError) -> str:
    lines: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        message = error["msg"]
        input_value = error.get("input")
        lines.append(f"- {location}: {message} (input: {input_value!r})")
    return "\n".join(lines)


def _run_id() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _resolve_repo(task: TaskConfig, task_file: Path) -> Path:
    repo = Path(task.repo).expanduser()
    candidates = [
        repo,
        task_file.parent / repo,
        Path.cwd() / repo,
    ]
    for candidate in candidates:
        if candidate.exists():
            return ensure_git_repo(candidate.resolve())
    raise RuntimeError(f"Task repo does not exist or is not accessible: {task.repo}")


def _instruction_for(task: TaskConfig) -> str:
    criteria = "\n".join(f"- {item}" for item in task.success_criteria)
    return (
        f"{task.title}\n\n"
        f"Task type: {task.type.value}\n\n"
        f"Description:\n{task.description}\n\n"
        f"Instructions:\n{task.instructions}\n\n"
        f"Success criteria:\n{criteria}\n"
    )


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _serialize_command_group(result: CommandGroupResult) -> dict[str, object]:
    return {
        "passed": result.passed,
        "commands": [
            {
                "name": command.name,
                "command": command.command,
                "exit_code": command.exit_code,
                "duration_seconds": command.duration_seconds,
                "timed_out": command.timed_out,
            }
            for command in result.commands
        ],
    }


def _unavailable_agent_result(agent_name: str) -> AgentExecutionResult:
    return AgentExecutionResult(
        agent_name=agent_name,
        command=None,
        exit_code=127,
        stdout="",
        stderr=f"Agent {agent_name!r} is not available on PATH.\n",
        duration_seconds=0.0,
    )


def _run_one_agent(
    *,
    agent_name: str,
    task: TaskConfig,
    task_file: Path,
    repo_root: Path,
    run_root: Path,
    keep_worktree: bool,
    timeout: int | None,
) -> dict[str, object]:
    agent = get_agent(agent_name)
    agent_dir = run_root / agent_name
    agent_dir.mkdir(parents=True, exist_ok=True)

    worktree_path = Path.cwd() / ".agentarena" / "worktrees" / run_root.name / agent_name
    worktree = None
    setup_result = CommandGroupResult()
    test_result = CommandGroupResult()
    patch = ""
    diff_stats = DiffStats([], 0, 0, 0)
    started = time.monotonic()

    try:
        worktree = create_worktree(repo_root, worktree_path)
        setup_result = run_commands(task.setup_commands(), worktree.path)

        if setup_result.passed is False:
            agent_result = AgentExecutionResult(
                agent_name=agent_name,
                command=None,
                exit_code=1,
                stdout="",
                stderr="Setup failed; agent execution was skipped.\n",
                duration_seconds=0.0,
            )
        elif not agent.is_available():
            agent_result = _unavailable_agent_result(agent_name)
        else:
            agent_result = agent.run(_instruction_for(task), worktree.path, timeout=timeout)

        patch, diff_stats = collect_diff(worktree.path)
        if setup_result.passed is not False:
            test_result = run_commands(task.test_commands_for_run(), worktree.path)
    finally:
        if worktree is not None and not keep_worktree:
            remove_worktree(repo_root, worktree.path)

    duration = time.monotonic() - started
    violations = check_constraints(task.constraints, diff_stats, patch)
    constraints_passed = not violations
    score = calculate_score(
        tests_passed=test_result.passed,
        constraints_passed=constraints_passed,
        violations=violations,
        diff_stats=diff_stats,
        duration_seconds=duration,
    )
    failures = analyze_failures(
        setup_passed=setup_result.passed,
        agent_exit_code=agent_result.exit_code,
        tests_passed=test_result.passed,
        diff_stats=diff_stats,
        violations=violations,
    )

    _write_text(agent_dir / "stdout.log", agent_result.stdout)
    _write_text(agent_dir / "stderr.log", agent_result.stderr)
    _write_text(agent_dir / "test.log", _format_command_logs(setup_result, test_result))
    _write_text(agent_dir / "diff.patch", patch)

    result: dict[str, object] = {
        "run_id": run_root.name,
        "task": {
            "id": task.id,
            "title": task.title,
            "type": task.type.value,
            "task_file": str(task_file),
            "repo": str(repo_root),
        },
        "agent": agent_name,
        "worktree": str(worktree_path),
        "worktree_kept": keep_worktree,
        "agent_exit_code": agent_result.exit_code,
        "agent_command": agent_result.command,
        "setup": _serialize_command_group(setup_result),
        "tests_passed": test_result.passed,
        "test": _serialize_command_group(test_result),
        "constraints_passed": constraints_passed,
        "constraint_violations": [violation.to_dict() for violation in violations],
        "diff": diff_stats.to_dict(),
        "score": score.score,
        "score_breakdown": score.breakdown,
        "duration_seconds": duration,
        "failures": failures,
        "files": {
            "stdout": "stdout.log",
            "stderr": "stderr.log",
            "test": "test.log",
            "diff": "diff.patch",
            "summary": "summary.md",
        },
    }

    _write_text(agent_dir / "summary.md", _summary_markdown(result))
    (agent_dir / "result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return result


def _format_command_logs(
    setup_result: CommandGroupResult,
    test_result: CommandGroupResult,
) -> str:
    sections: list[str] = []
    for label, group in (("setup", setup_result), ("test", test_result)):
        sections.append(f"# {label} commands")
        if not group.commands:
            sections.append("No commands configured.")
            continue
        for command in group.commands:
            sections.append(f"## {command.name}: {command.command}")
            sections.append(f"exit_code={command.exit_code}")
            sections.append("### stdout")
            sections.append(command.stdout or "")
            sections.append("### stderr")
            sections.append(command.stderr or "")
    return "\n".join(sections)


def _summary_markdown(result: dict[str, object]) -> str:
    diff = result["diff"]
    assert isinstance(diff, dict)
    violations = result["constraint_violations"]
    failures = result["failures"]
    return "\n".join(
        [
            f"# {result['agent']} - {result['task']['id']}",  # type: ignore[index]
            "",
            f"- Score: {result['score']}",
            f"- Tests passed: {result['tests_passed']}",
            f"- Constraints passed: {result['constraints_passed']}",
            f"- Files changed: {diff['changed_file_count'] if 'changed_file_count' in diff else len(diff['changed_files'])}",
            f"- Diff lines: {diff['total_diff_lines']}",
            f"- Violations: {len(violations) if isinstance(violations, list) else 0}",
            f"- Failures: {', '.join(failures) if isinstance(failures, list) and failures else 'none'}",
            "",
        ]
    )


def _load_results(runs_dir: Path) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    if not runs_dir.exists():
        return results
    for result_file in runs_dir.glob("*/*/result.json"):
        results.append(json.loads(result_file.read_text(encoding="utf-8")))
    return sorted(results, key=lambda item: int(item.get("score", 0)), reverse=True)


def _result_row(result: dict[str, object], rank: int) -> list[str]:
    task = result.get("task", {})
    diff = result.get("diff", {})
    violations = result.get("constraint_violations", [])
    failures = result.get("failures", [])
    return [
        str(rank),
        str(result.get("agent", "")),
        str(task.get("id", "") if isinstance(task, dict) else ""),
        str(task.get("type", "") if isinstance(task, dict) else ""),
        str(result.get("score", 0)),
        str(result.get("tests_passed")),
        str(len(diff.get("changed_files", [])) if isinstance(diff, dict) else 0),
        str(diff.get("total_diff_lines", 0) if isinstance(diff, dict) else 0),
        str(len(violations) if isinstance(violations, list) else 0),
        f"{float(result.get('duration_seconds', 0.0)):.1f}s",
        ", ".join(failures) if isinstance(failures, list) else "",
    ]


@app.command()
def init(
    path: Annotated[
        Path,
        typer.Argument(
            help="Repository or workspace path to initialize for AgentArena Local.",
        ),
    ] = Path("."),
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing AgentArena config."),
    ] = False,
) -> None:
    """Create the local AgentArena configuration directory."""
    try:
        result = init_workspace(path, force=force)
    except FileExistsError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    action = "Updated" if result.overwritten else "Created"
    console.print(f"[green]{action}[/green] AgentArena workspace at {result.config_dir}")


@app.command()
def validate(
    task_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Path to task.yaml.",
        ),
    ],
) -> None:
    """Validate a task.yaml file."""
    try:
        task = load_task(task_file)
    except ValidationError as exc:
        console.print(f"[red]Invalid task:[/red] {task_file}")
        console.print(_format_validation_error(exc))
        raise typer.Exit(code=1) from exc
    except (ValueError, yaml.YAMLError) as exc:
        console.print(f"[red]Invalid task:[/red] {task_file}")
        console.print(str(exc))
        raise typer.Exit(code=1) from exc

    console.print(f"[green]Valid task[/green]: {task.id} ({task.type})")


@app.command()
def schema() -> None:
    """Print the JSON schema for task.yaml."""
    console.print_json(data=TaskConfig.model_json_schema())


@app.command()
def run(
    task_file: Annotated[
        Path,
        typer.Option("--task", exists=True, file_okay=True, dir_okay=False, readable=True),
    ],
    agent: Annotated[
        str | None,
        typer.Option("--agent", help="Single agent name to run."),
    ] = None,
    agents: Annotated[
        str | None,
        typer.Option("--agents", help="Comma-separated agent names to run."),
    ] = None,
    keep_worktree: Annotated[
        bool,
        typer.Option("--keep-worktree", help="Keep agent worktrees after the run."),
    ] = False,
    timeout: Annotated[
        int | None,
        typer.Option("--timeout", help="Agent execution timeout in seconds."),
    ] = None,
) -> None:
    """Run one or more AI coding agents against a task."""
    if not agent and not agents:
        agent_names = ["manual"]
    elif agents:
        agent_names = [item.strip() for item in agents.split(",") if item.strip()]
    else:
        agent_names = [agent or "manual"]

    try:
        task = load_task(task_file)
        repo_root = _resolve_repo(task, task_file.resolve())
    except (ValueError, ValidationError, yaml.YAMLError, RuntimeError) as exc:
        console.print(f"[red]Cannot run task:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    run_root = Path.cwd() / ".agentarena" / "runs" / f"{_run_id()}_{task.id}"
    run_root.mkdir(parents=True, exist_ok=True)

    results = []
    for agent_name in agent_names:
        console.print(f"[cyan]Running[/cyan] {agent_name} on {task.id}")
        try:
            results.append(
                _run_one_agent(
                    agent_name=agent_name,
                    task=task,
                    task_file=task_file.resolve(),
                    repo_root=repo_root,
                    run_root=run_root,
                    keep_worktree=keep_worktree,
                    timeout=timeout,
                )
            )
        except Exception as exc:
            console.print(f"[red]Agent {agent_name} failed:[/red] {exc}")
            raise typer.Exit(code=1) from exc

    console.print(f"[green]Saved run[/green] {run_root}")
    for result in sorted(results, key=lambda item: int(item.get("score", 0)), reverse=True):
        console.print(
            f"{result['agent']}: score={result['score']} "
            f"tests={result['tests_passed']} failures={result['failures']}"
        )


@app.command()
def leaderboard() -> None:
    """Print and save the AgentArena leaderboard."""
    runs_dir = Path.cwd() / ".agentarena" / "runs"
    results = _load_results(runs_dir)

    table = Table(title="AgentArena Leaderboard")
    columns = ["Rank", "Agent", "Task", "Type", "Score", "Tests", "Files", "Diff", "Violations", "Time", "Failures"]
    for column in columns:
        table.add_column(column)
    for index, result in enumerate(results, start=1):
        table.add_row(*_result_row(result, index))
    console.print(table)

    leaderboard_json = [
        dict(zip(columns, _result_row(result, index), strict=True))
        for index, result in enumerate(results, start=1)
    ]
    reports_dir = Path.cwd() / ".agentarena" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "leaderboard.json").write_text(
        json.dumps(leaderboard_json, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md_lines = ["# AgentArena Leaderboard", "", "|" + "|".join(columns) + "|", "|" + "|".join(["---"] * len(columns)) + "|"]
    for index, result in enumerate(results, start=1):
        md_lines.append("|" + "|".join(_result_row(result, index)) + "|")
    _write_text(reports_dir / "leaderboard.md", "\n".join(md_lines) + "\n")
    console.print(f"[green]Saved[/green] {reports_dir / 'leaderboard.md'}")


@app.command()
def report(
    format: Annotated[
        str,
        typer.Option("--format", help="Report format. v0.2 supports html."),
    ] = "html",
) -> None:
    """Generate a report for saved runs."""
    if format != "html":
        console.print("[red]Only --format html is supported in v0.2.[/red]")
        raise typer.Exit(code=1)

    reports_dir = Path.cwd() / ".agentarena" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    results = _load_results(Path.cwd() / ".agentarena" / "runs")
    from jinja2 import Template

    html = Template(REPORT_TEMPLATE).render(results=results)
    output = reports_dir / "latest-report.html"
    _write_text(output, html)
    console.print(f"[green]Saved[/green] {output}")


@app.command()
def dashboard() -> None:
    """Generate a Plotly dashboard for saved runs."""
    reports_dir = Path.cwd() / ".agentarena" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    results = _load_results(Path.cwd() / ".agentarena" / "runs")
    labels = [f"{result['agent']} / {result['task']['id']}" for result in results]  # type: ignore[index]
    scores = [result.get("score", 0) for result in results]
    diff_lines = [result.get("diff", {}).get("total_diff_lines", 0) for result in results]  # type: ignore[union-attr]
    files = [len(result.get("diff", {}).get("changed_files", [])) for result in results]  # type: ignore[union-attr]
    durations = [result.get("duration_seconds", 0) for result in results]
    violations = [len(result.get("constraint_violations", [])) for result in results]

    output = reports_dir / "dashboard.html"
    from jinja2 import Template

    html = Template(DASHBOARD_TEMPLATE).render(
        labels=json.dumps(labels),
        scores=json.dumps(scores),
        diff_lines=json.dumps(diff_lines),
        files=json.dumps(files),
        durations=json.dumps(durations),
        violations=json.dumps(violations),
    )
    _write_text(output, html)
    console.print(f"[green]Saved[/green] {output}")


REPORT_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AgentArena Local Report</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 32px; color: #1f2937; }
    table { border-collapse: collapse; width: 100%; margin: 16px 0 32px; }
    th, td { border: 1px solid #d1d5db; padding: 8px; text-align: left; vertical-align: top; }
    th { background: #f3f4f6; }
    section { margin-bottom: 32px; }
    code { background: #f3f4f6; padding: 2px 4px; }
  </style>
</head>
<body>
  <h1>AgentArena Local Report</h1>
  <section>
    <h2>Leaderboard</h2>
    <table>
      <thead><tr><th>Rank</th><th>Agent</th><th>Task</th><th>Type</th><th>Score</th><th>Tests</th><th>Files</th><th>Diff</th><th>Violations</th><th>Time</th><th>Failures</th></tr></thead>
      <tbody>
      {% for result in results %}
        <tr>
          <td>{{ loop.index }}</td>
          <td>{{ result.agent }}</td>
          <td>{{ result.task.id }}</td>
          <td>{{ result.task.type }}</td>
          <td>{{ result.score }}</td>
          <td>{{ result.tests_passed }}</td>
          <td>{{ result.diff.changed_files|length }}</td>
          <td>{{ result.diff.total_diff_lines }}</td>
          <td>{{ result.constraint_violations|length }}</td>
          <td>{{ "%.1f"|format(result.duration_seconds) }}s</td>
          <td>{{ result.failures|join(", ") }}</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </section>
  {% for result in results %}
  <section>
    <h2>{{ result.agent }} - {{ result.task.id }}</h2>
    <p><strong>Task:</strong> {{ result.task.title }} (<code>{{ result.task.type }}</code>)</p>
    <p><strong>Score:</strong> {{ result.score }}</p>
    <p><strong>Failures:</strong> {{ result.failures|join(", ") if result.failures else "none" }}</p>
    <h3>Constraint Violations</h3>
    <ul>
      {% for violation in result.constraint_violations %}
      <li>{{ violation.severity }}: {{ violation.message }}</li>
      {% else %}
      <li>none</li>
      {% endfor %}
    </ul>
    <h3>Files</h3>
    <ul>
      <li><a href="../runs/{{ result.run_id }}/{{ result.agent }}/diff.patch">diff.patch</a></li>
      <li><a href="../runs/{{ result.run_id }}/{{ result.agent }}/test.log">test.log</a></li>
      <li><a href="../runs/{{ result.run_id }}/{{ result.agent }}/stdout.log">stdout.log</a></li>
      <li><a href="../runs/{{ result.run_id }}/{{ result.agent }}/stderr.log">stderr.log</a></li>
    </ul>
  </section>
  {% endfor %}
</body>
</html>
"""


DASHBOARD_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AgentArena Local Dashboard</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body { font-family: Arial, sans-serif; margin: 32px; color: #1f2937; }
    .chart { height: 360px; margin-bottom: 28px; }
  </style>
</head>
<body>
  <h1>AgentArena Local Dashboard</h1>
  <div id="score" class="chart"></div>
  <div id="diff" class="chart"></div>
  <div id="files" class="chart"></div>
  <div id="duration" class="chart"></div>
  <div id="violations" class="chart"></div>
  <script>
    const labels = {{ labels }};
    const charts = [
      ["score", "Score", {{ scores }}],
      ["diff", "Diff lines", {{ diff_lines }}],
      ["files", "Files changed", {{ files }}],
      ["duration", "Duration seconds", {{ durations }}],
      ["violations", "Violations", {{ violations }}],
    ];
    for (const [id, title, values] of charts) {
      Plotly.newPlot(id, [{ type: "bar", x: labels, y: values }], {
        title,
        template: "plotly_white",
        margin: { l: 48, r: 24, t: 48, b: 96 },
        xaxis: { tickangle: -30 }
      });
    }
  </script>
</body>
</html>
"""
