from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import shutil
from typing import Literal

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agentarena_local.agents.registry import get_agent, list_agents
from agentarena_local.cli import (
    _abtest_row,
    _best_result,
    _filter_results,
    _load_abtest_results,
    _load_results,
    _overall_rows,
    _parse_agent_names,
    _resolve_repo,
    _result_row,
    _run_id,
    _run_one_agent,
)
from agentarena_local.config import load_config
from agentarena_local.gitops.worktree import create_worktree
from agentarena_local.results.browser import latest_run, list_runs
from agentarena_local.tasks import load_task


INTERACTIVE_AGENTS = {"manual", "cursor", "cline", "windsurf"}
WEB_DEFAULT_TIMEOUT_SECONDS = 120


class RunRequest(BaseModel):
    task_file: str = Field(default="examples/python_debug_login/task.yaml")
    agents: list[str] = Field(default_factory=lambda: ["codex"])
    keep_worktree: bool = False
    timeout: int | None = WEB_DEFAULT_TIMEOUT_SECONDS


class ReportRequest(BaseModel):
    kind: Literal["report", "dashboard"] = "report"


class CursorSessionRequest(BaseModel):
    task_file: str = Field(default="examples/python_debug_login/task.yaml")


@dataclass
class JobState:
    id: str
    status: Literal["queued", "running", "succeeded", "failed"] = "queued"
    logs: list[str] = field(default_factory=list)
    results: list[dict[str, object]] = field(default_factory=list)
    error: str | None = None
    cancel_requested: bool = False
    current_process: subprocess.Popen[str] | None = None
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None


JOBS: dict[str, JobState] = {}
JOBS_LOCK = threading.Lock()


def _json_path(path: Path) -> str:
    return str(path.resolve())


def _append_log(job: JobState, message: str) -> None:
    stamp = time.strftime("%H:%M:%S")
    with JOBS_LOCK:
        job.logs.append(f"[{stamp}] {message}")


def _kill_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if subprocess._mswindows:  # type: ignore[attr-defined]
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
        if process.poll() is None:
            process.kill()
        return
    process.kill()


def _register_process(job: JobState, process: subprocess.Popen[str]) -> None:
    with JOBS_LOCK:
        job.current_process = process
        cancelled = job.cancel_requested
    if cancelled:
        _kill_process_tree(process)


def _task_title(task_file: Path) -> str:
    try:
        raw = yaml.safe_load(task_file.read_text(encoding="utf-8")) or {}
    except Exception:
        return task_file.stem
    return str(raw.get("title") or raw.get("id") or task_file.stem)


def _discover_tasks(root: Path) -> list[dict[str, str]]:
    files = sorted(root.glob("examples/**/task.yaml"))
    configured = root / "tasks"
    if configured.exists():
        files.extend(sorted(configured.glob("**/*.yaml")))
    seen: set[Path] = set()
    tasks: list[dict[str, str]] = []
    for task_file in files:
        resolved = task_file.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        tasks.append(
            {
                "path": str(task_file.relative_to(root)).replace("\\", "/")
                if resolved.is_relative_to(root.resolve())
                else str(resolved),
                "title": _task_title(task_file),
            }
        )
    return tasks


def _instruction_markdown(task_file: Path) -> str:
    task = load_task(task_file)
    criteria = "\n".join(f"- {item}" for item in task.success_criteria)
    return "\n".join(
        [
            f"# AgentArena Task: {task.title}",
            "",
            f"- Task id: `{task.id}`",
            f"- Type: `{task.type.value}`",
            f"- Source task file: `{task_file}`",
            "",
            "## Description",
            "",
            task.description,
            "",
            "## Instructions",
            "",
            task.instructions,
            "",
            "## Success Criteria",
            "",
            criteria,
            "",
            "After finishing in Cursor, return to AgentArena and run the benchmark for the changed worktree or inspect the diff manually.",
            "",
        ]
    )


def _resolve_cursor_command() -> str | None:
    return shutil.which("cursor.cmd") or shutil.which("cursor")


def _run_job(job: JobState, request: RunRequest) -> None:
    config = load_config(Path.cwd())
    task_file = Path(request.task_file).expanduser()
    if not task_file.is_absolute():
        task_file = config.root / task_file
    agent_names = [agent.lower() for agent in request.agents if agent.strip()]
    agent_names = _parse_agent_names(None, ",".join(agent_names))
    interactive = [agent for agent in agent_names if agent in INTERACTIVE_AGENTS]
    if interactive:
        names = ", ".join(interactive)
        raise RuntimeError(
            f"Interactive agents are not supported from the Web GUI yet: {names}. "
            "Use the CLI for manual-mode agents."
        )
    effective_timeout = request.timeout if request.timeout is not None else WEB_DEFAULT_TIMEOUT_SECONDS
    effective_keep_worktree = request.keep_worktree or config.keep_worktree

    with JOBS_LOCK:
        job.status = "running"
    _append_log(job, f"Loading task {task_file}")

    try:
        task = load_task(task_file)
        repo_root = _resolve_repo(task, task_file.resolve())
        run_root = config.runs_dir / f"{_run_id()}_{task.id}"
        run_root.mkdir(parents=True, exist_ok=True)
        _append_log(job, f"Created run {run_root}")

        for agent_name in agent_names:
            if job.cancel_requested:
                raise RuntimeError("Run cancelled")
            _append_log(job, f"Running {agent_name} on {task.id} (timeout {effective_timeout}s)")
            stop_heartbeat = threading.Event()

            def heartbeat() -> None:
                started = time.monotonic()
                while not stop_heartbeat.wait(10):
                    elapsed = int(time.monotonic() - started)
                    _append_log(job, f"{agent_name} still running ({elapsed}s elapsed)")

            heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
            heartbeat_thread.start()
            result = _run_one_agent(
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
                on_agent_process=lambda process: _register_process(job, process),
            )
            stop_heartbeat.set()
            heartbeat_thread.join(timeout=1)
            with JOBS_LOCK:
                job.current_process = None
            with JOBS_LOCK:
                job.results.append(result)
            _append_log(
                job,
                f"{agent_name}: score={result['score']} tests={result['tests_passed']}",
            )

        with JOBS_LOCK:
            job.status = "succeeded"
            job.finished_at = time.time()
        _append_log(job, "Run finished")
    except Exception as exc:
        with JOBS_LOCK:
            job.status = "failed"
            job.error = str(exc)
            job.finished_at = time.time()
        _append_log(job, f"Run failed: {exc}")


def _leaderboard_payload(task_type: str | None = None, overall: bool = False) -> dict[str, object]:
    config = load_config(Path.cwd())
    results = _load_abtest_results(config.runs_dir) if task_type == "abtest" else _load_results(config.runs_dir)
    if task_type != "abtest":
        results = _filter_results(results, task_type)

    if overall:
        columns = ["Rank", "Agent", "Avg Score", "Planning", "Debug", "Generation", "Runs", "Pass Rate"]
        rows = _overall_rows(results)
    else:
        columns = ["Rank", "Agent", "Task", "Type", "Score", "Tests", "Files", "Diff", "Violations", "Time", "Failures"]
        if task_type == "abtest":
            columns = ["Rank", "Variant", "Agent", "Task", "Score", "Tests", "Files", "Diff", "Violations", "Time", "Failures"]
            rows = [_abtest_row(result, index) for index, result in enumerate(results, start=1)]
        else:
            rows = [_result_row(result, index) for index, result in enumerate(results, start=1)]

    return {
        "columns": columns,
        "rows": [dict(zip(columns, row, strict=True)) for row in rows],
        "best": _best_result(results),
    }


def create_app() -> FastAPI:
    app = FastAPI(title="AgentArena Local Web API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, object]:
        config = load_config(Path.cwd())
        return {
            "ok": True,
            "root": _json_path(config.root),
            "runs_dir": _json_path(config.runs_dir),
            "reports_dir": _json_path(config.reports_dir),
        }

    @app.get("/api/options")
    def options() -> dict[str, object]:
        config = load_config(Path.cwd())
        agent_rows = []
        for name in list_agents():
            agent = get_agent(name)
            interactive = name in INTERACTIVE_AGENTS
            agent_rows.append(
                {
                    "name": name,
                    "available": (agent.is_available() and not interactive) or (name == "cursor" and _resolve_cursor_command() is not None),
                    "interactive": interactive,
                    "gui": name == "cursor" and _resolve_cursor_command() is not None,
                }
            )
        return {
            "root": _json_path(config.root),
            "tasks": _discover_tasks(config.root),
            "agents": agent_rows,
        }

    @app.post("/api/run")
    def start_run(request: RunRequest) -> dict[str, object]:
        job = JobState(id=uuid.uuid4().hex[:12])
        with JOBS_LOCK:
            JOBS[job.id] = job
        thread = threading.Thread(target=_run_job, args=(job, request), daemon=True)
        thread.start()
        return {"job_id": job.id, "status": job.status}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, object]:
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Job not found")
            return {
                "id": job.id,
                "status": job.status,
                "logs": list(job.logs),
                "results": list(job.results),
                "error": job.error,
                "cancel_requested": job.cancel_requested,
                "started_at": job.started_at,
                "finished_at": job.finished_at,
            }

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict[str, object]:
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Job not found")
            job.cancel_requested = True
            process = job.current_process
            if job.status in {"queued", "running"}:
                job.status = "failed"
                job.error = "Run cancelled"
                job.finished_at = time.time()
        if process is not None:
            _kill_process_tree(process)
        _append_log(job, "Run cancelled")
        return {"job_id": job.id, "status": job.status}

    @app.get("/api/leaderboard")
    def leaderboard(task_type: str | None = None, overall: bool = False) -> dict[str, object]:
        return _leaderboard_payload(task_type=task_type, overall=overall)

    @app.get("/api/runs")
    def runs() -> dict[str, object]:
        config = load_config(Path.cwd())
        latest = latest_run(config.runs_dir)
        return {
            "latest": latest.to_dict() if latest else None,
            "runs": [summary.to_dict() for summary in list_runs(config.runs_dir)],
        }

    @app.post("/api/reports")
    def reports(request: ReportRequest) -> dict[str, object]:
        from agentarena_local.cli import dashboard, report

        if request.kind == "dashboard":
            dashboard()
            path = load_config(Path.cwd()).reports_dir / "dashboard.html"
        else:
            report()
            path = load_config(Path.cwd()).reports_dir / "latest-report.html"
        return {"path": _json_path(path), "kind": request.kind}

    @app.post("/api/cursor/session")
    def cursor_session(request: CursorSessionRequest) -> dict[str, object]:
        command = _resolve_cursor_command()
        if command is None:
            raise HTTPException(status_code=404, detail="Cursor command was not found on PATH")

        config = load_config(Path.cwd())
        task_file = Path(request.task_file).expanduser()
        if not task_file.is_absolute():
            task_file = config.root / task_file
        task = load_task(task_file)
        repo_root = _resolve_repo(task, task_file.resolve())
        session_id = f"{_run_id()}_{task.id}_cursor"
        worktree_path = config.root / ".agentarena" / "worktrees" / session_id
        create_worktree(repo_root, worktree_path)
        instruction_file = worktree_path / "AGENTARENA_TASK.md"
        instruction_file.write_text(_instruction_markdown(task_file.resolve()), encoding="utf-8")
        subprocess.Popen(
            [command, str(worktree_path)],
            cwd=worktree_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {
            "session_id": session_id,
            "worktree": _json_path(worktree_path),
            "instruction_file": _json_path(instruction_file),
            "command": command,
        }

    return app


app = create_app()
