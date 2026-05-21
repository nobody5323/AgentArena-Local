import json
from pathlib import Path

from agentarena_local.results.browser import find_run, latest_run, list_runs


def _write_result(runs_dir: Path, run_id: str, agent: str, score: int) -> None:
    result_dir = runs_dir / run_id / agent
    result_dir.mkdir(parents=True)
    (result_dir / "result.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "agent": agent,
                "task": {"id": "task", "type": "debug"},
                "score": score,
            }
        ),
        encoding="utf-8",
    )


def test_runs_browser_lists_latest_and_find(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _write_result(runs_dir, "20240101_task", "codex", 70)
    _write_result(runs_dir, "20240102_task", "claude", 90)

    runs = list_runs(runs_dir)

    assert runs[0].run_id == "20240102_task"
    assert latest_run(runs_dir).best_score == 90  # type: ignore[union-attr]
    assert find_run(runs_dir, "20240101").agents == ["codex"]  # type: ignore[union-attr]
