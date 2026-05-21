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
