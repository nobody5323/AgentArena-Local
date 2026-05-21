import json
from pathlib import Path

from typer.testing import CliRunner

from agentarena_local.cli import app


runner = CliRunner()


def _write_result(path: Path, agent: str, score: int) -> None:
    result_dir = path / ".agentarena" / "runs" / f"run_{agent}" / agent
    result_dir.mkdir(parents=True)
    (result_dir / "result.json").write_text(
        json.dumps(
            {
                "run_id": f"run_{agent}",
                "agent": agent,
                "task": {"id": "task", "type": "debug"},
                "score": score,
                "tests_passed": True,
                "diff": {"changed_files": ["app.py"], "total_diff_lines": 3},
                "constraint_violations": [],
                "duration_seconds": 1.0,
                "failures": [],
            }
        ),
        encoding="utf-8",
    )


def test_leaderboard_sorts_by_score(tmp_path: Path, monkeypatch) -> None:
    _write_result(tmp_path, "low", 20)
    _write_result(tmp_path, "high", 90)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["leaderboard"])

    assert result.exit_code == 0
    leaderboard = json.loads(
        (tmp_path / ".agentarena" / "reports" / "leaderboard.json").read_text(
            encoding="utf-8"
        )
    )
    assert leaderboard[0]["Agent"] == "high"
    assert leaderboard[1]["Agent"] == "low"


def test_leaderboard_type_filters_results(tmp_path: Path, monkeypatch) -> None:
    _write_result(tmp_path, "debug_agent", 80)
    generation_dir = tmp_path / ".agentarena" / "runs" / "run_generation" / "gen"
    generation_dir.mkdir(parents=True)
    (generation_dir / "result.json").write_text(
        json.dumps(
            {
                "run_id": "run_generation",
                "agent": "gen",
                "task": {"id": "task", "type": "generation"},
                "score": 50,
                "tests_passed": True,
                "diff": {"changed_files": ["app.py"], "total_diff_lines": 3},
                "constraint_violations": [],
                "duration_seconds": 1.0,
                "failures": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["leaderboard", "--type", "generation"])

    assert result.exit_code == 0
    leaderboard = json.loads((tmp_path / ".agentarena" / "reports" / "leaderboard.json").read_text(encoding="utf-8"))
    assert len(leaderboard) == 1
    assert leaderboard[0]["Agent"] == "gen"


def test_overall_leaderboard_aggregates_average_score(tmp_path: Path, monkeypatch) -> None:
    _write_result(tmp_path, "agent", 100)
    second_dir = tmp_path / ".agentarena" / "runs" / "run_second" / "agent"
    second_dir.mkdir(parents=True)
    (second_dir / "result.json").write_text(
        json.dumps(
            {
                "run_id": "run_second",
                "agent": "agent",
                "task": {"id": "task2", "type": "planning"},
                "score": 50,
                "tests_passed": None,
                "diff": {"changed_files": [], "total_diff_lines": 0},
                "constraint_violations": [],
                "duration_seconds": 1.0,
                "failures": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["leaderboard", "--overall"])

    assert result.exit_code == 0
    leaderboard = json.loads((tmp_path / ".agentarena" / "reports" / "leaderboard.json").read_text(encoding="utf-8"))
    assert leaderboard[0]["Agent"] == "agent"
    assert leaderboard[0]["Avg Score"] == "75.0"
