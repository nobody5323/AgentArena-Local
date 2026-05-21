from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    task: str
    task_type: str
    agents: list[str]
    best_score: int
    result_count: int
    path: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _result_files(run_dir: Path) -> list[Path]:
    return sorted(run_dir.glob("**/result.json"))


def summarize_run(run_dir: Path) -> RunSummary | None:
    result_files = _result_files(run_dir)
    if not result_files:
        return None
    results = [json.loads(path.read_text(encoding="utf-8")) for path in result_files]
    task = results[0].get("task", {})
    scores = [int(result.get("score", 0)) for result in results]
    agents = sorted({str(result.get("agent", "")) for result in results})
    return RunSummary(
        run_id=run_dir.name,
        task=str(task.get("id", "")) if isinstance(task, dict) else "",
        task_type=str(task.get("type", "")) if isinstance(task, dict) else "",
        agents=agents,
        best_score=max(scores) if scores else 0,
        result_count=len(results),
        path=str(run_dir),
    )


def list_runs(runs_dir: Path) -> list[RunSummary]:
    if not runs_dir.exists():
        return []
    summaries = [
        summary
        for summary in (summarize_run(path) for path in sorted(runs_dir.iterdir()))
        if summary is not None
    ]
    return sorted(summaries, key=lambda summary: summary.run_id, reverse=True)


def latest_run(runs_dir: Path) -> RunSummary | None:
    runs = list_runs(runs_dir)
    return runs[0] if runs else None


def find_run(runs_dir: Path, run_id: str) -> RunSummary | None:
    direct = summarize_run(runs_dir / run_id)
    if direct is not None:
        return direct
    matches = [summary for summary in list_runs(runs_dir) if summary.run_id.startswith(run_id)]
    return matches[0] if matches else None
