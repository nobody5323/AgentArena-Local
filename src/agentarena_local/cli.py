from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Annotated

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from agentarena_local.abtest.experiment import save_abtest_outputs
from agentarena_local.abtest.variant import load_variants
from agentarena_local.agents.base import AgentExecutionResult
from agentarena_local.agents.registry import get_agent
from agentarena_local.config import AppConfig, init_workspace, load_config
from agentarena_local.gitops.diff import DiffStats, collect_diff
from agentarena_local.gitops.worktree import create_worktree, ensure_git_repo, remove_worktree
from agentarena_local.metrics.constraints import check_constraints
from agentarena_local.metrics.failure_analysis import (
    analyze_failures,
    extend_generation_failures,
    extend_planning_failures,
)
from agentarena_local.metrics.feature import evaluate_feature_slice
from agentarena_local.metrics.scorer import calculate_generation_score, calculate_score
from agentarena_local.metrics.scorer import calculate_strict_generation_score
from agentarena_local.metrics.strict import summarize_strict_evaluation
from agentarena_local.metrics.test_runner import CommandGroupResult, run_commands
from agentarena_local.planning.plan_collector import save_plan
from agentarena_local.planning.plan_report import save_planning_result
from agentarena_local.planning.plan_scorer import score_plan
from agentarena_local.results.browser import find_run, latest_run, list_runs
from agentarena_local.suite import append_jsonl, completed_keys, load_suite, read_jsonl, summarize_suite
from agentarena_local.tasks import TaskConfig, load_task

app = typer.Typer(
    name="agentarena",
    help="AgentArena Local: evaluate AI coding agents in local Git repositories.",
    no_args_is_help=True,
)
suite_app = typer.Typer(help="Run task suites and aggregate agent comparisons.")
app.add_typer(suite_app, name="suite")
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


def _parse_agent_names(agent: str | None, agents: str | None) -> list[str]:
    if not agent and not agents:
        return ["manual"]
    if agents:
        return [item.strip() for item in agents.split(",") if item.strip()]
    return [agent or "manual"]


def _resolve_repo(task: TaskConfig, task_file: Path) -> Path:
    repo = Path(task.repo).expanduser()
    candidates = [
        repo,
        task_file.parent / repo,
        Path.cwd() / repo,
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                return ensure_git_repo(candidate.resolve())
            except RuntimeError:
                continue
    raise RuntimeError(f"Task repo does not exist or is not accessible: {task.repo}")


def _apply_agent_command_config(agent: object, config: AppConfig, agent_name: str) -> None:
    command = config.agent_commands.get(agent_name)
    if command and hasattr(agent, "executable"):
        setattr(agent, "executable", command)


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
    path.write_text(content or "", encoding="utf-8")


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
    runs_dir: Path,
    worktrees_dir: Path,
    keep_worktree: bool,
    timeout: int | None,
    config: AppConfig | None = None,
    agents_md_source: Path | None = None,
    variant: str | None = None,
    on_agent_process: object | None = None,
) -> dict[str, object]:
    agent = get_agent(agent_name)
    if config is not None:
        _apply_agent_command_config(agent, config, agent_name)
    agent_dir = run_root / agent_name
    agent_dir.mkdir(parents=True, exist_ok=True)

    run_relative = str(run_root.relative_to(runs_dir)).replace("\\", "/")
    worktree_key = run_relative.replace("/", "_")
    worktree_path = worktrees_dir / worktree_key / agent_name
    worktree = None
    setup_result = CommandGroupResult()
    baseline_result = CommandGroupResult()
    fail_to_pass_result = CommandGroupResult()
    pass_to_pass_result = CommandGroupResult()
    hidden_result = CommandGroupResult()
    test_result = CommandGroupResult()
    patch = ""
    diff_stats = DiffStats([], 0, 0, 0)
    started = time.monotonic()

    try:
        worktree = create_worktree(repo_root, worktree_path)
        if agents_md_source is not None:
            shutil.copyfile(agents_md_source, worktree.path / "AGENTS.md")
        setup_result = run_commands(task.setup_commands(), worktree.path)
        if setup_result.passed is not False and task.has_strict_evaluation():
            baseline_result = run_commands(task.baseline_commands(), worktree.path)

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
        elif on_agent_process is not None and hasattr(agent, "run_with_callback"):
            agent_result = agent.run_with_callback(
                _instruction_for(task),
                worktree.path,
                timeout=timeout,
                on_process=on_agent_process,
            )
        else:
            agent_result = agent.run(_instruction_for(task), worktree.path, timeout=timeout)

        patch, diff_stats = collect_diff(worktree.path)
        if setup_result.passed is not False:
            if task.has_strict_evaluation():
                fail_to_pass_result = run_commands(task.fail_to_pass_commands(), worktree.path)
                pass_to_pass_result = run_commands(task.pass_to_pass_commands(), worktree.path)
                hidden_result = run_commands(task.hidden_commands(), worktree.path)
                combined_commands = [
                    *fail_to_pass_result.commands,
                    *pass_to_pass_result.commands,
                    *hidden_result.commands,
                ]
                combined_passed = None
                if combined_commands:
                    combined_passed = all(command.succeeded for command in combined_commands)
                test_result = CommandGroupResult(commands=combined_commands, passed=combined_passed)
            else:
                test_result = run_commands(task.test_commands_for_run(), worktree.path)
    finally:
        if worktree is not None and not keep_worktree:
            remove_worktree(repo_root, worktree.path)

    duration = time.monotonic() - started
    violations = check_constraints(task.constraints, diff_stats, patch)
    constraints_passed = not violations
    failures = analyze_failures(
        setup_passed=setup_result.passed,
        agent_exit_code=agent_result.exit_code,
        tests_passed=test_result.passed,
        diff_stats=diff_stats,
        violations=violations,
    )
    score = calculate_score(
        tests_passed=test_result.passed,
        constraints_passed=constraints_passed,
        violations=violations,
        diff_stats=diff_stats,
        duration_seconds=duration,
    )
    planning_result: dict[str, object] | None = None
    feature_result: dict[str, object] | None = None
    warnings: list[str] = []
    strict_result = summarize_strict_evaluation(
        baseline=baseline_result,
        fail_to_pass=fail_to_pass_result,
        pass_to_pass=pass_to_pass_result,
        hidden=hidden_result,
    )

    if task.type.value == "planning":
        failures = [failure for failure in failures if failure != "no_code_changed"]
        plan_path = save_plan(agent_dir, task.planning.output_file, agent_result.stdout)
        planning_score = score_plan(
            plan_text=agent_result.stdout,
            expected_keywords=task.planning.expected_keywords,
            modified_code=diff_stats.total_diff_lines > 0,
        )
        failures = extend_planning_failures(
            failures,
            modified_code=planning_score.modified_code,
            keyword_hit_rate=planning_score.keyword_hit_rate,
        )
        save_planning_result(
            agent_dir,
            plan_file=plan_path.name,
            score=planning_score,
            failures=failures,
        )
        planning_result = {
            "plan_file": plan_path.name,
            **planning_score.to_dict(),
        }
        score = type(score)(score=planning_score.score, breakdown={
            "no_code_changed": 0 if planning_score.modified_code else 30,
            "expected_keywords": round(planning_score.keyword_hit_rate * 40),
            "test_plan": 15 if planning_score.has_test_plan else 0,
            "risks": 15 if planning_score.has_risks else 0,
        })
    elif strict_result.enabled:
        if strict_result.task_valid is False and "strict_baseline_not_failing" not in failures:
            failures.append("strict_baseline_not_failing")
        if strict_result.fail_to_pass_passed is False and "fail_to_pass_failed" not in failures:
            failures.append("fail_to_pass_failed")
        if strict_result.pass_to_pass_passed is False and "pass_to_pass_failed" not in failures:
            failures.append("pass_to_pass_failed")
        if strict_result.hidden_passed is False and "hidden_failed" not in failures:
            failures.append("hidden_failed")
        feature_eval = None
        feature_completeness = 25
        if task.type.value == "generation":
            feature_eval = evaluate_feature_slice(
                diff_stats=diff_stats,
                patch=patch,
                expected_files_may_change=task.expected_files_may_change,
                feature_checks=task.feature_checks,
            )
            failures = extend_generation_failures(
                failures,
                missing_required_patterns=feature_eval.missing_required_patterns,
                unexpected_files=feature_eval.unexpected_files,
            )
            warnings.extend(feature_eval.warnings)
            feature_result = feature_eval.to_dict()
            feature_completeness = feature_eval.completeness
        score = calculate_strict_generation_score(
            strict=strict_result,
            feature_completeness=feature_completeness,
            constraints_passed=constraints_passed,
            violations=violations,
            diff_stats=diff_stats,
            duration_seconds=duration,
        )
    elif task.type.value == "generation":
        feature_eval = evaluate_feature_slice(
            diff_stats=diff_stats,
            patch=patch,
            expected_files_may_change=task.expected_files_may_change,
            feature_checks=task.feature_checks,
        )
        failures = extend_generation_failures(
            failures,
            missing_required_patterns=feature_eval.missing_required_patterns,
            unexpected_files=feature_eval.unexpected_files,
        )
        warnings.extend(feature_eval.warnings)
        feature_result = feature_eval.to_dict()
        score = calculate_generation_score(
            tests_passed=test_result.passed,
            feature_completeness=feature_eval.completeness,
            constraints_passed=constraints_passed,
            diff_stats=diff_stats,
        )

    _write_text(agent_dir / "stdout.log", agent_result.stdout)
    _write_text(agent_dir / "stderr.log", agent_result.stderr)
    _write_text(
        agent_dir / "test.log",
        _format_command_logs(
            setup_result,
            test_result,
            baseline_result=baseline_result,
            fail_to_pass_result=fail_to_pass_result,
            pass_to_pass_result=pass_to_pass_result,
            hidden_result=hidden_result,
        ),
    )
    _write_text(agent_dir / "diff.patch", patch)

    result: dict[str, object] = {
        "run_id": run_relative,
        "task": {
            "id": task.id,
            "title": task.title,
            "type": task.type.value,
            "task_file": str(task_file),
            "repo": str(repo_root),
        },
        "agent": agent_name,
        "variant": variant,
        "worktree": str(worktree_path),
        "worktree_kept": keep_worktree,
        "agent_exit_code": agent_result.exit_code,
        "agent_command": agent_result.command,
        "setup": _serialize_command_group(setup_result),
        "baseline": _serialize_command_group(baseline_result),
        "tests_passed": test_result.passed,
        "test": _serialize_command_group(test_result),
        "strict": strict_result.to_dict(),
        "fail_to_pass": _serialize_command_group(fail_to_pass_result),
        "pass_to_pass": _serialize_command_group(pass_to_pass_result),
        "hidden": _serialize_command_group(hidden_result),
        "constraints_passed": constraints_passed,
        "constraint_violations": [violation.to_dict() for violation in violations],
        "diff": diff_stats.to_dict(),
        "score": score.score,
        "score_breakdown": score.breakdown,
        "duration_seconds": duration,
        "failures": failures,
        "warnings": warnings,
        "planning": planning_result,
        "feature": feature_result,
        "files": {
            "stdout": "stdout.log",
            "stderr": "stderr.log",
            "test": "test.log",
            "diff": "diff.patch",
            "summary": "summary.md",
        },
    }
    if planning_result:
        result["files"]["plan"] = planning_result["plan_file"]  # type: ignore[index]
        result["files"]["planning_result"] = "planning_result.json"  # type: ignore[index]

    _write_text(agent_dir / "summary.md", _summary_markdown(result))
    (agent_dir / "result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return result


def _format_command_logs(
    setup_result: CommandGroupResult,
    test_result: CommandGroupResult,
    *,
    baseline_result: CommandGroupResult | None = None,
    fail_to_pass_result: CommandGroupResult | None = None,
    pass_to_pass_result: CommandGroupResult | None = None,
    hidden_result: CommandGroupResult | None = None,
) -> str:
    sections: list[str] = []
    groups = [
        ("setup", setup_result),
        ("baseline", baseline_result),
        ("fail_to_pass", fail_to_pass_result),
        ("pass_to_pass", pass_to_pass_result),
        ("hidden", hidden_result),
        ("test", test_result),
    ]
    for label, group in groups:
        if group is None:
            continue
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
    strict = result.get("strict", {})
    strict_lines: list[str] = []
    if isinstance(strict, dict) and strict.get("enabled"):
        strict_lines = [
            f"- Resolved: {strict.get('resolved')}",
            f"- Fail-to-pass: {strict.get('fail_to_pass_passed')}",
            f"- Pass-to-pass: {strict.get('pass_to_pass_passed')}",
            f"- Hidden: {strict.get('hidden_passed')}",
        ]
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
            *strict_lines,
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


def _load_abtest_results(runs_dir: Path) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    if not runs_dir.exists():
        return results
    for result_file in runs_dir.glob("abtest_*/*/*/result.json"):
        results.append(json.loads(result_file.read_text(encoding="utf-8")))
    return sorted(results, key=lambda item: int(item.get("score", 0)), reverse=True)


def _filter_results(results: list[dict[str, object]], task_type: str | None) -> list[dict[str, object]]:
    if task_type is None:
        return results
    if task_type == "abtest":
        return [result for result in results if result.get("variant")]
    return [
        result
        for result in results
        if isinstance(result.get("task"), dict) and result["task"].get("type") == task_type
    ]


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


def _abtest_row(result: dict[str, object], rank: int) -> list[str]:
    base = _result_row(result, rank)
    return [base[0], str(result.get("variant", "")), base[1], base[2], base[4], base[5], base[6], base[7], base[8], base[9], base[10]]


def _overall_rows(results: list[dict[str, object]]) -> list[list[str]]:
    by_agent: dict[str, list[dict[str, object]]] = {}
    for result in results:
        by_agent.setdefault(str(result.get("agent", "")), []).append(result)
    rows: list[list[str]] = []
    for agent, agent_results in by_agent.items():
        avg = sum(float(item.get("score", 0)) for item in agent_results) / len(agent_results)
        pass_count = sum(1 for item in agent_results if item.get("tests_passed") is True)
        def avg_for(kind: str) -> str:
            typed = [item for item in agent_results if isinstance(item.get("task"), dict) and item["task"].get("type") == kind]
            if not typed:
                return "-"
            return f"{sum(float(item.get('score', 0)) for item in typed) / len(typed):.1f}"
        rows.append([
            agent,
            f"{avg:.1f}",
            avg_for("planning"),
            avg_for("debug"),
            avg_for("generation"),
            str(len(agent_results)),
            f"{(pass_count / len(agent_results)) * 100:.0f}%",
        ])
    rows.sort(key=lambda row: float(row[1]), reverse=True)
    return [[str(index), *row] for index, row in enumerate(rows, start=1)]


def _failure_distribution(results: list[dict[str, object]]) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for result in results:
        failures = result.get("failures", [])
        if isinstance(failures, list):
            for failure in failures:
                distribution[str(failure)] = distribution.get(str(failure), 0) + 1
    return dict(sorted(distribution.items(), key=lambda item: item[1], reverse=True))


def _best_result(results: list[dict[str, object]]) -> dict[str, object] | None:
    if not results:
        return None
    return max(results, key=lambda item: int(item.get("score", 0)))


def _suite_result_row(stat: object) -> list[str]:
    hidden = getattr(stat, "hidden_pass_rate")
    regression = getattr(stat, "regression_pass_rate")
    return [
        str(getattr(stat, "agent")),
        f"{getattr(stat, 'pass_at_1') * 100:.0f}%",
        f"{getattr(stat, 'pass_at_k') * 100:.0f}%",
        f"{getattr(stat, 'avg_score'):.1f}",
        f"{getattr(stat, 'median_score'):.1f}",
        "-" if hidden is None else f"{hidden * 100:.0f}%",
        "-" if regression is None else f"{regression * 100:.0f}%",
        f"{getattr(stat, 'timeout_rate') * 100:.0f}%",
        f"{getattr(stat, 'avg_duration'):.1f}s",
        str(getattr(stat, "unique_wins")),
    ]


def _write_suite_report(results_file: Path, rows: list[dict[str, object]]) -> Path:
    stats = summarize_suite(rows)
    report_path = results_file.with_suffix(".summary.md")
    columns = [
        "Agent",
        "pass@1",
        "pass@k",
        "Avg Score",
        "Median",
        "Hidden",
        "Regression",
        "Timeout",
        "Avg Time",
        "Unique Wins",
    ]
    lines = [
        "# AgentArena Suite Summary",
        "",
        f"Results: `{results_file}`",
        "",
        "|" + "|".join(columns) + "|",
        "|" + "|".join(["---"] * len(columns)) + "|",
    ]
    for stat in stats:
        lines.append("|" + "|".join(_suite_result_row(stat)) + "|")
    lines.append("")
    lines.append("## Failure Distribution")
    for stat in stats:
        failures = stat.failure_distribution
        label = ", ".join(f"{key}: {value}" for key, value in failures.items()) if failures else "none"
        lines.append(f"- {stat.agent}: {label}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


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


@suite_app.command("validate")
def suite_validate(
    suite_file: Annotated[
        Path,
        typer.Option("--suite", exists=True, file_okay=True, dir_okay=False, readable=True),
    ],
) -> None:
    """Validate a suite.yaml file."""
    try:
        suite = load_suite(suite_file)
    except (ValueError, ValidationError, yaml.YAMLError) as exc:
        console.print(f"[red]Invalid suite:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]Valid suite[/green]: {suite.id} ({len(suite.tasks)} tasks, tries={suite.tries})")


@suite_app.command("run")
def suite_run(
    suite_file: Annotated[
        Path,
        typer.Option("--suite", exists=True, file_okay=True, dir_okay=False, readable=True),
    ],
    agents: Annotated[
        str,
        typer.Option("--agents", help="Comma-separated agent names to run."),
    ],
    tries: Annotated[
        int | None,
        typer.Option("--tries", help="Override suite tries."),
    ] = None,
    timeout: Annotated[
        int | None,
        typer.Option("--timeout", help="Override agent timeout in seconds."),
    ] = None,
    results_file: Annotated[
        Path | None,
        typer.Option("--results", help="JSONL results file."),
    ] = None,
    resume: Annotated[
        bool,
        typer.Option("--resume", help="Skip completed agent/task/try rows already in the JSONL file."),
    ] = False,
) -> None:
    """Run a suite and append one JSONL row per agent/task/try."""
    config = load_config(Path.cwd())
    try:
        suite = load_suite(suite_file)
    except (ValueError, ValidationError, yaml.YAMLError) as exc:
        console.print(f"[red]Cannot run suite:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    agent_names = _parse_agent_names(None, agents)
    effective_tries = tries if tries is not None else suite.tries
    effective_timeout = timeout if timeout is not None else suite.timeout_seconds or config.default_timeout_seconds
    output = results_file or config.root / ".agentarena" / "results" / f"{suite.id}_{_run_id()}.jsonl"
    existing = read_jsonl(output) if resume else []
    done = completed_keys(existing)

    rows: list[dict[str, object]] = list(existing)
    for task_entry in suite.tasks:
        task_file = Path(task_entry)
        if not task_file.is_absolute():
            task_file = suite_file.parent / task_file
            if not task_file.exists():
                task_file = config.root / task_entry
        try:
            task = load_task(task_file)
            repo_root = _resolve_repo(task, task_file.resolve())
        except (ValueError, ValidationError, yaml.YAMLError, RuntimeError) as exc:
            console.print(f"[red]Cannot load suite task {task_entry}:[/red] {exc}")
            raise typer.Exit(code=1) from exc

        for agent_name in agent_names:
            for try_index in range(1, effective_tries + 1):
                key = (agent_name, task.id, try_index)
                if resume and key in done:
                    console.print(f"[yellow]Skipping[/yellow] {agent_name} {task.id} try={try_index}")
                    continue
                run_root = config.runs_dir / f"{_run_id()}_{suite.id}_{task.id}_try{try_index}"
                run_root.mkdir(parents=True, exist_ok=True)
                console.print(f"[cyan]Suite[/cyan] {suite.id}: {agent_name} on {task.id} try={try_index}")
                result = _run_one_agent(
                    agent_name=agent_name,
                    task=task,
                    task_file=task_file.resolve(),
                    repo_root=repo_root,
                    run_root=run_root,
                    runs_dir=config.runs_dir,
                    worktrees_dir=config.root / ".agentarena" / "worktrees",
                    keep_worktree=False,
                    timeout=effective_timeout,
                    config=config,
                )
                result["suite"] = {"id": suite.id, "suite_file": str(suite_file.resolve())}
                result["try_index"] = try_index
                append_jsonl(output, result)
                rows.append(result)

    report_path = _write_suite_report(output, rows)
    console.print(f"[green]Saved suite results[/green] {output}")
    console.print(f"[green]Saved suite summary[/green] {report_path}")
    for stat in summarize_suite(rows):
        console.print(
            f"{stat.agent}: pass@1={stat.pass_at_1:.0%} "
            f"pass@k={stat.pass_at_k:.0%} avg={stat.avg_score:.1f} "
            f"hidden={'-' if stat.hidden_pass_rate is None else f'{stat.hidden_pass_rate:.0%}'} "
            f"unique_wins={stat.unique_wins}"
        )


@suite_app.command("report")
def suite_report(
    results_file: Annotated[
        Path,
        typer.Option("--results", exists=True, file_okay=True, dir_okay=False, readable=True),
    ],
) -> None:
    """Summarize a suite JSONL file."""
    rows = read_jsonl(results_file)
    report_path = _write_suite_report(results_file, rows)
    table = Table(title="AgentArena Suite Summary")
    columns = ["Agent", "pass@1", "pass@k", "Avg Score", "Median", "Hidden", "Regression", "Timeout", "Avg Time", "Unique Wins"]
    for column in columns:
        table.add_column(column)
    for stat in summarize_suite(rows):
        table.add_row(*_suite_result_row(stat))
    console.print(table)
    console.print(f"[green]Saved[/green] {report_path}")


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
    config = load_config(Path.cwd())
    agent_names = _parse_agent_names(agent, agents)
    effective_timeout = timeout if timeout is not None else config.default_timeout_seconds
    effective_keep_worktree = keep_worktree or config.keep_worktree

    try:
        task = load_task(task_file)
        repo_root = _resolve_repo(task, task_file.resolve())
    except (ValueError, ValidationError, yaml.YAMLError, RuntimeError) as exc:
        console.print(f"[red]Cannot run task:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    run_root = config.runs_dir / f"{_run_id()}_{task.id}"
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
                    runs_dir=config.runs_dir,
                    worktrees_dir=config.root / ".agentarena" / "worktrees",
                    keep_worktree=effective_keep_worktree,
                    timeout=effective_timeout,
                    config=config,
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
def leaderboard(
    task_type: Annotated[
        str | None,
        typer.Option("--type", help="Filter by debug, generation, planning, or abtest."),
    ] = None,
    overall: Annotated[
        bool,
        typer.Option("--overall", help="Aggregate average scores by agent."),
    ] = False,
) -> None:
    """Print and save the AgentArena leaderboard."""
    config = load_config(Path.cwd())
    runs_dir = config.runs_dir
    results = _load_results(runs_dir)
    if task_type == "abtest":
        results = _load_abtest_results(runs_dir)
    else:
        results = _filter_results(results, task_type)

    reports_dir = config.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)

    if overall:
        table = Table(title="AgentArena Overall Leaderboard")
        columns = ["Rank", "Agent", "Avg Score", "Planning", "Debug", "Generation", "Runs", "Pass Rate"]
        rows = _overall_rows(results)
        for column in columns:
            table.add_column(column)
        for row in rows:
            table.add_row(*row)
        console.print(table)
        (reports_dir / "leaderboard.json").write_text(
            json.dumps([dict(zip(columns, row, strict=True)) for row in rows], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        md_lines = ["# AgentArena Overall Leaderboard", "", "|" + "|".join(columns) + "|", "|" + "|".join(["---"] * len(columns)) + "|"]
        for row in rows:
            md_lines.append("|" + "|".join(row) + "|")
        _write_text(reports_dir / "leaderboard.md", "\n".join(md_lines) + "\n")
        console.print(f"[green]Saved[/green] {reports_dir / 'leaderboard.md'}")
        return

    table = Table(title=f"AgentArena Leaderboard{f' ({task_type})' if task_type else ''}")
    columns = ["Rank", "Agent", "Task", "Type", "Score", "Tests", "Files", "Diff", "Violations", "Time", "Failures"]
    if task_type == "abtest":
        columns = ["Rank", "Variant", "Agent", "Task", "Score", "Tests", "Files", "Diff", "Violations", "Time", "Failures"]
    for column in columns:
        table.add_column(column)
    for index, result in enumerate(results, start=1):
        table.add_row(*(_abtest_row(result, index) if task_type == "abtest" else _result_row(result, index)))
    console.print(table)

    leaderboard_json = [
        dict(zip(columns, _abtest_row(result, index) if task_type == "abtest" else _result_row(result, index), strict=True))
        for index, result in enumerate(results, start=1)
    ]
    (reports_dir / "leaderboard.json").write_text(
        json.dumps(leaderboard_json, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md_lines = ["# AgentArena Leaderboard", "", "|" + "|".join(columns) + "|", "|" + "|".join(["---"] * len(columns)) + "|"]
    for index, result in enumerate(results, start=1):
        row = _abtest_row(result, index) if task_type == "abtest" else _result_row(result, index)
        md_lines.append("|" + "|".join(row) + "|")
    _write_text(reports_dir / "leaderboard.md", "\n".join(md_lines) + "\n")
    console.print(f"[green]Saved[/green] {reports_dir / 'leaderboard.md'}")


@app.command()
def abtest(
    task_file: Annotated[
        Path,
        typer.Option("--task", exists=True, file_okay=True, dir_okay=False, readable=True),
    ],
    variants: Annotated[
        Path,
        typer.Option("--variants", exists=True, file_okay=False, dir_okay=True, readable=True),
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
    """Run an AGENTS.md variant experiment."""
    config = load_config(Path.cwd())
    agent_names = _parse_agent_names(agent, agents)
    effective_timeout = timeout if timeout is not None else config.default_timeout_seconds
    effective_keep_worktree = keep_worktree or config.keep_worktree
    variant_specs = load_variants(variants)
    if not variant_specs:
        console.print(f"[red]No variants with AGENTS.md found in[/red] {variants}")
        raise typer.Exit(code=1)

    try:
        task = load_task(task_file)
        repo_root = _resolve_repo(task, task_file.resolve())
    except (ValueError, ValidationError, yaml.YAMLError, RuntimeError) as exc:
        console.print(f"[red]Cannot run A/B test:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    abtest_root = config.runs_dir / f"abtest_{_run_id()}_{task.id}"
    results: list[dict[str, object]] = []
    for variant_spec in variant_specs:
        for agent_name in agent_names:
            console.print(f"[cyan]A/B[/cyan] variant={variant_spec.name} agent={agent_name}")
            result = _run_one_agent(
                agent_name=agent_name,
                task=task,
                task_file=task_file.resolve(),
                repo_root=repo_root,
                run_root=abtest_root / variant_spec.name,
                runs_dir=config.runs_dir,
                worktrees_dir=config.root / ".agentarena" / "worktrees",
                keep_worktree=effective_keep_worktree,
                timeout=effective_timeout,
                config=config,
                agents_md_source=variant_spec.agents_md,
                variant=variant_spec.name,
            )
            result_file = abtest_root / variant_spec.name / agent_name / "result.json"
            result_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            results.append(result)

    results.sort(key=lambda item: int(item.get("score", 0)), reverse=True)
    rows = [_abtest_row(result, index) for index, result in enumerate(results, start=1)]
    save_abtest_outputs(abtest_root, rows, results)
    reports_dir = config.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)
    save_abtest_outputs(reports_dir, rows, results)
    console.print(f"[green]Saved A/B test[/green] {abtest_root}")


@app.command("runs")
def runs_command(
    latest: Annotated[
        bool,
        typer.Option("--latest", help="Show only the latest run and latest report path."),
    ] = False,
) -> None:
    """List historical AgentArena runs."""
    config = load_config(Path.cwd())
    summaries = [latest_run(config.runs_dir)] if latest else list_runs(config.runs_dir)
    summaries = [summary for summary in summaries if summary is not None]

    table = Table(title="AgentArena Runs")
    for column in ["Run ID", "Task", "Type", "Agents", "Best Score", "Results", "Path"]:
        table.add_column(column)
    for summary in summaries:
        table.add_row(
            summary.run_id,
            summary.task,
            summary.task_type,
            ", ".join(summary.agents),
            str(summary.best_score),
            str(summary.result_count),
            summary.path,
        )
    console.print(table)
    if latest:
        report_path = config.reports_dir / "latest-report.html"
        console.print(f"Latest report: {report_path}")


@app.command()
def show(run_id: Annotated[str, typer.Argument(help="Run id or unique prefix.")]) -> None:
    """Show a saved run summary."""
    config = load_config(Path.cwd())
    summary = find_run(config.runs_dir, run_id)
    if summary is None:
        console.print(f"[red]Run not found:[/red] {run_id}")
        raise typer.Exit(code=1)
    console.print_json(data=summary.to_dict())


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

    config = load_config(Path.cwd())
    reports_dir = config.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = config.runs_dir
    results = _load_results(runs_dir)
    abtest_results = _load_abtest_results(runs_dir)
    all_results = sorted([*results, *abtest_results], key=lambda item: int(item.get("score", 0)), reverse=True)
    best = _best_result(all_results)
    from jinja2 import Template

    html = Template(REPORT_TEMPLATE).render(
        results=all_results,
        abtest_results=abtest_results,
        failures=_failure_distribution(all_results),
        best=best,
    )
    output = reports_dir / "latest-report.html"
    _write_text(output, html)
    console.print(f"[green]Saved[/green] {output}")


@app.command()
def dashboard() -> None:
    """Generate a Plotly dashboard for saved runs."""
    config = load_config(Path.cwd())
    reports_dir = config.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = config.runs_dir
    results = [*_load_results(runs_dir), *_load_abtest_results(runs_dir)]
    labels = [f"{result['agent']} / {result['task']['id']}" for result in results]  # type: ignore[index]
    scores = [result.get("score", 0) for result in results]
    diff_lines = [result.get("diff", {}).get("total_diff_lines", 0) for result in results]  # type: ignore[union-attr]
    files = [len(result.get("diff", {}).get("changed_files", [])) for result in results]  # type: ignore[union-attr]
    durations = [result.get("duration_seconds", 0) for result in results]
    violations = [len(result.get("constraint_violations", [])) for result in results]
    type_labels = ["planning", "debug", "generation"]
    type_scores = [
        sum(float(result.get("score", 0)) for result in results if isinstance(result.get("task"), dict) and result["task"].get("type") == task_type)
        / max(1, sum(1 for result in results if isinstance(result.get("task"), dict) and result["task"].get("type") == task_type))
        for task_type in type_labels
    ]
    agents = sorted({str(result.get("agent", "")) for result in results})
    pass_rates = [
        (
            sum(1 for result in results if result.get("agent") == agent and result.get("tests_passed") is True)
            / max(1, sum(1 for result in results if result.get("agent") == agent))
        ) * 100
        for agent in agents
    ]
    variant_labels = sorted({str(result.get("variant", "")) for result in results if result.get("variant")})
    variant_scores = [
        sum(float(result.get("score", 0)) for result in results if result.get("variant") == variant)
        / max(1, sum(1 for result in results if result.get("variant") == variant))
        for variant in variant_labels
    ]
    failures = _failure_distribution(results)

    output = reports_dir / "dashboard.html"
    from jinja2 import Template

    html = Template(DASHBOARD_TEMPLATE).render(
        labels=json.dumps(labels),
        scores=json.dumps(scores),
        diff_lines=json.dumps(diff_lines),
        files=json.dumps(files),
        durations=json.dumps(durations),
        violations=json.dumps(violations),
        type_labels=json.dumps(type_labels),
        type_scores=json.dumps(type_scores),
        agents=json.dumps(agents),
        pass_rates=json.dumps(pass_rates),
        variant_labels=json.dumps(variant_labels),
        variant_scores=json.dumps(variant_scores),
        failure_labels=json.dumps(list(failures.keys())),
        failure_counts=json.dumps(list(failures.values())),
    )
    _write_text(output, html)
    console.print(f"[green]Saved[/green] {output}")


@app.command()
def gui() -> None:
    """Launch the FastAPI-backed Web GUI."""
    web_dir = Path.cwd() / "web"
    if not web_dir.exists():
        console.print("[red]Web GUI directory not found.[/red]")
        raise typer.Exit(code=1)

    api_command = [
        sys.executable,
        "-m",
        "uvicorn",
        "agentarena_local.web_api:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8765",
    ]
    web_command = ["npm", "run", "dev"]
    console.print("[green]Starting AgentArena Web GUI[/green]")
    console.print("API: http://127.0.0.1:8765")
    console.print("Web: http://127.0.0.1:5173")
    npm_executable = shutil.which("npm.cmd") or shutil.which("npm")
    if npm_executable is None:
        console.print("[red]npm was not found on PATH. Install Node.js 18+ to run the Web GUI.[/red]")
        raise typer.Exit(code=1)
    web_command = [npm_executable, "run", "dev"]
    api_process = subprocess.Popen(api_command, cwd=Path.cwd())
    try:
        web_process = subprocess.Popen(web_command, cwd=web_dir)
        try:
            web_process.wait()
        finally:
            web_process.terminate()
    finally:
        api_process.terminate()


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
    <h2>Recommendation</h2>
    {% if best %}
    <p>Best current result: <strong>{{ best.agent }}</strong>{% if best.variant %} with variant <strong>{{ best.variant }}</strong>{% endif %} on <code>{{ best.task.id }}</code>, score <strong>{{ best.score }}</strong>.</p>
    {% else %}
    <p>No results available yet.</p>
    {% endif %}
  </section>
  <section>
    <h2>Leaderboard</h2>
    <table>
      <thead><tr><th>Rank</th><th>Agent</th><th>Task</th><th>Type</th><th>Score</th><th>Tests</th><th>Files</th><th>Diff</th><th>Violations</th><th>Time</th><th>Failures</th></tr></thead>
      <tbody>
      {% for result in results %}
        <tr>
          <td>{{ loop.index }}</td>
          <td>{{ result.agent }}</td>
          <td>{{ result.task.id }}{% if result.variant %}<br><small>variant: {{ result.variant }}</small>{% endif %}</td>
          <td><code>{{ result.task.type }}</code></td>
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
  <section>
    <h2>A/B Test Comparison</h2>
    <table>
      <thead><tr><th>Variant</th><th>Agent</th><th>Task</th><th>Score</th><th>Failures</th></tr></thead>
      <tbody>
      {% for result in abtest_results %}
      <tr><td>{{ result.variant }}</td><td>{{ result.agent }}</td><td>{{ result.task.id }}</td><td>{{ result.score }}</td><td>{{ result.failures|join(", ") }}</td></tr>
      {% else %}
      <tr><td colspan="5">No A/B test results.</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </section>
  <section>
    <h2>Failure Reasons</h2>
    <ul>
      {% for failure, count in failures.items() %}
      <li>{{ failure }}: {{ count }}</li>
      {% else %}
      <li>none</li>
      {% endfor %}
    </ul>
  </section>
  {% for result in results %}
  <section>
    <h2>{{ result.agent }} - {{ result.task.id }}{% if best and result.run_id == best.run_id and result.agent == best.agent and result.variant == best.variant %} (winner){% endif %}</h2>
    <p><strong>Task:</strong> {{ result.task.title }} (<code>{{ result.task.type }}</code>)</p>
    {% if result.variant %}<p><strong>AGENTS.md variant:</strong> {{ result.variant }}</p>{% endif %}
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
      {% if result.files.plan %}<li><a href="../runs/{{ result.run_id }}/{{ result.agent }}/{{ result.files.plan }}">plan.md</a></li>{% endif %}
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
  <div id="types" class="chart"></div>
  <div id="variants" class="chart"></div>
    <div id="passrate" class="chart"></div>
    <div id="failures" class="chart"></div>
  <div id="diffscore" class="chart"></div>
  <script>
    const labels = {{ labels }};
    const charts = [
      ["score", "Score", {{ scores }}],
      ["diff", "Diff lines", {{ diff_lines }}],
      ["files", "Files changed", {{ files }}],
      ["duration", "Duration seconds", {{ durations }}],
      ["violations", "Violations", {{ violations }}],
      ["types", "Task type score comparison", {{ type_scores }}, {{ type_labels }}],
      ["variants", "AGENTS.md variant score comparison", {{ variant_scores }}, {{ variant_labels }}],
      ["passrate", "Pass rate by agent", {{ pass_rates }}, {{ agents }}],
      ["failures", "Failure reason distribution", {{ failure_counts }}, {{ failure_labels }}],
    ];
    for (const [id, title, values, customLabels] of charts) {
      Plotly.newPlot(id, [{ type: "bar", x: customLabels || labels, y: values }], {
        title,
        template: "plotly_white",
        margin: { l: 48, r: 24, t: 48, b: 96 },
        xaxis: { tickangle: -30 }
      });
    }
    Plotly.newPlot("diffscore", [{
      type: "scatter",
      mode: "markers",
      x: {{ diff_lines }},
      y: {{ scores }},
      text: labels,
      marker: { size: 11 }
    }], {
      title: "Diff vs score",
      xaxis: { title: "Diff lines" },
      yaxis: { title: "Score" },
      template: "plotly_white"
    });
  </script>
</body>
</html>
"""
